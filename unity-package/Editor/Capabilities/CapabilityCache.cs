using System;
using System.Collections.Generic;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Capabilities
{
    /// <summary>
    /// A single cached capability lookup for one backend base URL.
    /// </summary>
    public sealed class CapabilityCacheEntry
    {
        public CapabilityState State = CapabilityState.Unknown;
        public CapabilityDocument Document;
        public string ErrorMessage;
        public DateTime LastUpdatedUtc;

        internal CapabilityCacheEntry Clone()
        {
            return new CapabilityCacheEntry
            {
                State = State,
                Document = Document,
                ErrorMessage = ErrorMessage,
                LastUpdatedUtc = LastUpdatedUtc,
            };
        }
    }

    /// <summary>
    /// In-memory, per-editor-session cache of capability documents keyed by normalized
    /// backend base URL. Does not persist across domain reloads; a fresh reload simply
    /// re-fetches on next use, which is desirable since the backend process may itself
    /// have changed across a Unity domain reload.
    /// </summary>
    public sealed class CapabilityCache
    {
        readonly Dictionary<string, CapabilityCacheEntry> _entries =
            new Dictionary<string, CapabilityCacheEntry>(StringComparer.Ordinal);

        static readonly CapabilityCache SharedInstance = new CapabilityCache();

        public static CapabilityCache Shared => SharedInstance;

        public static string NormalizeKey(string backendBaseUrl)
        {
            return string.IsNullOrWhiteSpace(backendBaseUrl)
                ? string.Empty
                : backendBaseUrl.Trim().TrimEnd('/').ToLowerInvariant();
        }

        public CapabilityCacheEntry Get(string backendBaseUrl)
        {
            var key = NormalizeKey(backendBaseUrl);
            lock (_entries)
            {
                return _entries.TryGetValue(key, out var entry) ? entry.Clone() : new CapabilityCacheEntry();
            }
        }

        public void SetLoading(string backendBaseUrl)
        {
            var key = NormalizeKey(backendBaseUrl);
            lock (_entries)
            {
                var entry = GetOrCreate(key);
                entry.State = CapabilityState.Loading;
            }
        }

        public void SetReady(string backendBaseUrl, CapabilityDocument document)
        {
            var key = NormalizeKey(backendBaseUrl);
            lock (_entries)
            {
                var entry = GetOrCreate(key);
                entry.Document = document;
                entry.ErrorMessage = null;
                entry.LastUpdatedUtc = DateTime.UtcNow;

                var compatibility = CapabilityCompatibilityChecker.Check(document);
                if (compatibility.IsCompatible)
                {
                    entry.State = CapabilityState.Ready;
                }
                else
                {
                    entry.State = CapabilityState.Incompatible;
                    entry.ErrorMessage = string.Join(" ", compatibility.Reasons);
                }
            }
        }

        public void SetUnavailable(string backendBaseUrl, string errorMessage)
        {
            var key = NormalizeKey(backendBaseUrl);
            lock (_entries)
            {
                var entry = GetOrCreate(key);
                // A previously-Ready document becomes Stale (still shown, flagged as unverified)
                // rather than being discarded on a single failed refresh.
                entry.State = entry.Document != null ? CapabilityState.Stale : CapabilityState.Unavailable;
                entry.ErrorMessage = errorMessage;
                entry.LastUpdatedUtc = DateTime.UtcNow;
            }
        }

        public void Invalidate(string backendBaseUrl)
        {
            var key = NormalizeKey(backendBaseUrl);
            lock (_entries)
            {
                _entries.Remove(key);
            }
        }

        public void Clear()
        {
            lock (_entries)
            {
                _entries.Clear();
            }
        }

        CapabilityCacheEntry GetOrCreate(string key)
        {
            if (!_entries.TryGetValue(key, out var entry))
            {
                entry = new CapabilityCacheEntry();
                _entries[key] = entry;
            }

            return entry;
        }
    }
}
