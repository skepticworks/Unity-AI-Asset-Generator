using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Configuration;
using UnityEngine;

namespace UnityAiAssets.Editor.Models
{
    public sealed class ModelManagementState
    {
        public bool Busy;
        public string StatusMessage = "Idle";
        public string ErrorMessage;
        public ModelListDocument Catalog;
        public ModelDiskUsageDocument DiskUsage;
        public string SelectedModelId;
        public string HuggingFaceId = "";
        public string HuggingFaceRevision = "";
        public string StorageDirectoryDraft = "";

        public InstalledModelDocument Selected
        {
            get
            {
                if (Catalog == null || Catalog.Models == null || string.IsNullOrWhiteSpace(SelectedModelId))
                    return null;
                foreach (var model in Catalog.Models)
                {
                    if (model != null && model.Id == SelectedModelId)
                        return model;
                }

                return null;
            }
        }
    }

    /// <summary>
    /// Loads and mutates managed models through the backend API.
    /// Disk-size walks are explicit (Refresh Disk Usage), not OnGUI polling.
    /// </summary>
    public sealed class ModelManagementController
    {
        readonly Func<IGenerationApiClient> _clientFactory;
        CancellationTokenSource _cts;

        public ModelManagementController(Func<IGenerationApiClient> clientFactory = null)
        {
            _clientFactory = clientFactory ?? (() =>
            {
                return UnityAiAssetSettings.CreateApiClient();
            });
            State = new ModelManagementState();
        }

        public ModelManagementState State { get; }

        public bool IsBusy => State.Busy;

        public async Task RefreshAsync()
        {
            await RunAsync("Loading models…", async (client, token) =>
            {
                var catalog = await client.ListModelsAsync(token).ConfigureAwait(true);
                State.Catalog = catalog;
                if (string.IsNullOrWhiteSpace(State.StorageDirectoryDraft) && catalog.Storage != null)
                    State.StorageDirectoryDraft = catalog.Storage.Directory ?? string.Empty;
                if (State.Selected == null && catalog.Models != null && catalog.Models.Count > 0)
                    State.SelectedModelId = catalog.Models[0].Id;
                State.StatusMessage = catalog.Models.Count == 0
                    ? "No managed models installed."
                    : catalog.Models.Count + " managed model(s).";
            }).ConfigureAwait(true);
        }

        public async Task RefreshDiskUsageAsync()
        {
            await RunAsync("Calculating disk usage…", async (client, token) =>
            {
                State.DiskUsage = await client.RefreshModelDiskUsageAsync(token).ConfigureAwait(true);
                if (State.Catalog != null && State.DiskUsage != null)
                {
                    foreach (var pair in State.DiskUsage.Models)
                    {
                        foreach (var model in State.Catalog.Models)
                        {
                            if (model.Id == pair.Key)
                                model.SizeBytes = pair.Value;
                        }
                    }
                }

                State.StatusMessage = "Disk usage updated.";
            }).ConfigureAwait(true);
        }

        public async Task InstallHuggingFaceAsync()
        {
            var identifier = (State.HuggingFaceId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(identifier))
            {
                State.ErrorMessage = "Enter a Hugging Face repository id.";
                return;
            }

            await RunAsync("Installing model…", async (client, token) =>
            {
                var json = ModelInstallRequestJson.HuggingFace(
                    identifier, State.HuggingFaceRevision, null);
                var model = await client.InstallModelAsync(json, token).ConfigureAwait(true);
                State.SelectedModelId = model.Id;
                State.StatusMessage = "Installed " + model.Name + ".";
                await RefreshQuietAsync(client, token).ConfigureAwait(true);
            }).ConfigureAwait(true);
        }

        public async Task InstallLocalAsync(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                State.ErrorMessage = "Choose a local Diffusers model directory.";
                return;
            }

            await RunAsync("Copying local model…", async (client, token) =>
            {
                var json = ModelInstallRequestJson.LocalDirectory(path, null, null);
                var model = await client.InstallModelAsync(json, token).ConfigureAwait(true);
                State.SelectedModelId = model.Id;
                State.StatusMessage = "Installed " + model.Name + ".";
                await RefreshQuietAsync(client, token).ConfigureAwait(true);
            }).ConfigureAwait(true);
        }

        public async Task RevalidateSelectedAsync()
        {
            var selected = State.Selected;
            if (selected == null)
                return;
            await RunAsync("Revalidating…", async (client, token) =>
            {
                var model = await client.ValidateModelAsync(selected.Id, token).ConfigureAwait(true);
                ReplaceOrAdd(model);
                State.StatusMessage = model.Usable
                    ? "Validation succeeded."
                    : "Validation found problems.";
            }).ConfigureAwait(true);
        }

        public async Task ActivateSelectedAsync()
        {
            var selected = State.Selected;
            if (selected == null)
                return;
            await RunAsync("Activating model…", async (client, token) =>
            {
                var model = await client.ActivateModelAsync(selected.Id, token).ConfigureAwait(true);
                if (State.Catalog != null)
                {
                    foreach (var item in State.Catalog.Models)
                        item.Active = item.Id == model.Id;
                    State.Catalog.ActiveModelId = model.Id;
                }

                State.StatusMessage = "Active model is now " + model.Name + ".";
            }).ConfigureAwait(true);
        }

        public async Task DeleteSelectedAsync()
        {
            var selected = State.Selected;
            if (selected == null)
                return;
            await RunAsync("Deleting model…", async (client, token) =>
            {
                await client.DeleteModelAsync(selected.Id, confirm: true, token).ConfigureAwait(true);
                State.StatusMessage = "Deleted " + selected.Name + ".";
                State.SelectedModelId = null;
                await RefreshQuietAsync(client, token).ConfigureAwait(true);
            }).ConfigureAwait(true);
        }

        public async Task ApplyStorageDirectoryAsync()
        {
            var directory = (State.StorageDirectoryDraft ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(directory))
            {
                State.ErrorMessage = "Storage directory cannot be empty.";
                return;
            }

            await RunAsync("Updating storage directory…", async (client, token) =>
            {
                var storage = await client.UpdateModelStorageAsync(directory, token).ConfigureAwait(true);
                if (State.Catalog != null)
                    State.Catalog.Storage = storage;
                State.StorageDirectoryDraft = storage.Directory;
                await RefreshQuietAsync(client, token).ConfigureAwait(true);
                State.StatusMessage = "Storage directory updated.";
            }).ConfigureAwait(true);
        }

        public async Task SetOfflineAsync(bool enabled)
        {
            await RunAsync(enabled ? "Enabling offline mode…" : "Disabling offline mode…",
                async (client, token) =>
                {
                    var offline = await client.SetOfflineModeAsync(enabled, token).ConfigureAwait(true);
                    if (State.Catalog != null)
                        State.Catalog.OfflineMode = offline;
                    State.StatusMessage = offline
                        ? "Offline mode on. Remote installs are unavailable."
                        : "Offline mode off.";
                }).ConfigureAwait(true);
        }

        async Task RefreshQuietAsync(IGenerationApiClient client, CancellationToken token)
        {
            var catalog = await client.ListModelsAsync(token).ConfigureAwait(true);
            State.Catalog = catalog;
            if (catalog.Storage != null)
                State.StorageDirectoryDraft = catalog.Storage.Directory ?? State.StorageDirectoryDraft;
        }

        void ReplaceOrAdd(InstalledModelDocument model)
        {
            if (State.Catalog == null)
                State.Catalog = new ModelListDocument();
            if (State.Catalog.Models == null)
                State.Catalog.Models = new List<InstalledModelDocument>();
            for (var i = 0; i < State.Catalog.Models.Count; i++)
            {
                if (State.Catalog.Models[i].Id == model.Id)
                {
                    State.Catalog.Models[i] = model;
                    return;
                }
            }

            State.Catalog.Models.Add(model);
        }

        async Task RunAsync(string status, Func<IGenerationApiClient, CancellationToken, Task> action)
        {
            if (State.Busy)
                return;
            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            State.Busy = true;
            State.ErrorMessage = null;
            State.StatusMessage = status;
            try
            {
                using (var client = _clientFactory())
                {
                    await action(client, token).ConfigureAwait(true);
                }
            }
            catch (ApiException ex)
            {
                State.ErrorMessage = FormatApiError(ex);
                State.StatusMessage = "Model management failed.";
                Debug.LogWarning(ex);
            }
            catch (Exception ex)
            {
                State.ErrorMessage = ex.Message;
                State.StatusMessage = "Model management failed.";
                Debug.LogException(ex);
            }
            finally
            {
                State.Busy = false;
            }
        }

        static string FormatApiError(ApiException ex)
        {
            if (ex.AppErrorCode == "OFFLINE_OPERATION_UNAVAILABLE")
                return "Unavailable offline: " + ex.UserFacingMessage;
            if (string.IsNullOrWhiteSpace(ex.Message))
                return "Backend request failed.";
            return ex.Message;
        }
    }
}
