using System;
using System.Collections.Generic;

namespace UnityAiAssets.Editor.Api
{
    public sealed class ModelLicenseInfo
    {
        public bool Known;
        public string Name;
        public string Url;
        public string File;
        public string Identifier;

        public string Display
        {
            get
            {
                if (Known && !string.IsNullOrWhiteSpace(Name))
                    return Name;
                if (Known && !string.IsNullOrWhiteSpace(Identifier))
                    return Identifier;
                if (!string.IsNullOrWhiteSpace(File))
                    return "See " + File + " (identifier unknown)";
                return "Unknown";
            }
        }
    }

    public sealed class ModelValidationIssueInfo
    {
        public string Code;
        public string Message;
        public string Path;
    }

    public sealed class ModelValidationInfo
    {
        public string State;
        public string CheckedAt;
        public List<ModelValidationIssueInfo> Issues = new List<ModelValidationIssueInfo>();

        public bool IsValid => State == "valid";
    }

    public sealed class ModelCompatibilityInfo
    {
        public string SchemaName;
        public string SchemaVersion;
        public string SchemaStatus;
        public string Architecture;
        public string PipelineType;
        public string PipelineClass;
        public string ModelFamily;
        public List<string> SupportedOperations = new List<string>();
        public List<string> RequiredComponents = new List<string>();
        public string BackendEngine;
        public List<string> GenerationModes = new List<string>();

        public bool SchemaSupported => SchemaStatus == "supported";
    }

    public sealed class InstalledModelDocument
    {
        public string Id;
        public string Name;
        public string Version;
        public string Revision;
        public string Source;
        public string SourceIdentifier;
        public string SourceUrl;
        public ModelLicenseInfo License = new ModelLicenseInfo();
        public string ModelType;
        public string PipelineClass;
        public string Family;
        public string InstalledAt;
        public string Status;
        public bool Usable;
        public bool Active;
        public long? SizeBytes;
        public ModelValidationInfo Validation = new ModelValidationInfo();
        public ModelCompatibilityInfo Compatibility = new ModelCompatibilityInfo();
        public string HashAlgorithm;

        public string SizeLabel
        {
            get
            {
                if (!SizeBytes.HasValue || SizeBytes.Value < 0)
                    return "unknown";
                var bytes = SizeBytes.Value;
                if (bytes < 1024)
                    return bytes + " B";
                if (bytes < 1024 * 1024)
                    return (bytes / 1024.0).ToString("0.0") + " KB";
                if (bytes < 1024L * 1024 * 1024)
                    return (bytes / (1024.0 * 1024.0)).ToString("0.0") + " MB";
                return (bytes / (1024.0 * 1024.0 * 1024.0)).ToString("0.00") + " GB";
            }
        }

        public static bool TryParse(string json, out InstalledModelDocument document)
        {
            try
            {
                document = FromJsonNode(JsonNode.Parse(json));
                return document != null;
            }
            catch (Exception)
            {
                document = null;
                return false;
            }
        }

        public static InstalledModelDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
                throw new FormatException("Model document root must be a JSON object.");

            var licenseNode = root.Get("license");
            var validationNode = root.Get("validation");
            var compatibilityNode = root.Get("compatibility");
            var issuesNode = validationNode.Get("issues");

            var issues = new List<ModelValidationIssueInfo>();
            foreach (var issue in issuesNode.AsArray())
            {
                if (issue == null || !issue.IsObject)
                    continue;
                issues.Add(new ModelValidationIssueInfo
                {
                    Code = issue.Get("code").AsString(),
                    Message = issue.Get("message").AsString(),
                    Path = issue.Get("path").AsString(),
                });
            }

            return new InstalledModelDocument
            {
                Id = root.Get("id").AsString(),
                Name = root.Get("name").AsString(),
                Version = root.Get("version").AsString(),
                Revision = root.Get("revision").AsString(),
                Source = root.Get("source").AsString(),
                SourceIdentifier = root.Get("source_identifier").AsString(),
                SourceUrl = root.Get("source_url").AsString(),
                License = new ModelLicenseInfo
                {
                    Known = licenseNode.Get("known").AsBool(),
                    Name = licenseNode.Get("name").AsString(),
                    Url = licenseNode.Get("url").AsString(),
                    File = licenseNode.Get("file").AsString(),
                    Identifier = licenseNode.Get("identifier").AsString(),
                },
                ModelType = root.Get("model_type").AsString(),
                PipelineClass = root.Get("pipeline_class").AsString(),
                Family = root.Get("family").AsString(),
                InstalledAt = root.Get("installed_at").AsString(),
                Status = root.Get("status").AsString(),
                Usable = root.Get("usable").AsBool(),
                Active = root.Get("active").AsBool(),
                SizeBytes = root.Get("size_bytes").AsNullableLong(),
                Validation = new ModelValidationInfo
                {
                    State = validationNode.Get("state").AsString(),
                    CheckedAt = validationNode.Get("checked_at").AsString(),
                    Issues = issues,
                },
                Compatibility = new ModelCompatibilityInfo
                {
                    SchemaName = compatibilityNode.Get("schema_name").AsString(),
                    SchemaVersion = compatibilityNode.Get("schema_version").AsString(),
                    SchemaStatus = compatibilityNode.Get("schema_status").AsString(),
                    Architecture = compatibilityNode.Get("architecture").AsString(),
                    PipelineType = compatibilityNode.Get("pipeline_type").AsString(),
                    PipelineClass = compatibilityNode.Get("pipeline_class").AsString(),
                    ModelFamily = compatibilityNode.Get("model_family").AsString(),
                    SupportedOperations = compatibilityNode.Get("supported_operations").AsStringList(),
                    RequiredComponents = compatibilityNode.Get("required_components").AsStringList(),
                    BackendEngine = compatibilityNode.Get("backend_engine").AsString(),
                    GenerationModes = compatibilityNode.Get("generation_modes").AsStringList(),
                },
                HashAlgorithm = root.Get("hash_algorithm").AsString("sha256"),
            };
        }
    }

    public sealed class ModelStorageDocument
    {
        public string Directory;
        public bool Exists;
        public bool Accessible;
        public bool Writable;
        public bool Created;
        public string Issue;
        public List<string> SearchPaths = new List<string>();
        public long? FreeBytes;
        public long? TotalVolumeBytes;

        public static bool TryParse(string json, out ModelStorageDocument document)
        {
            try
            {
                document = FromJsonNode(JsonNode.Parse(json));
                return document != null;
            }
            catch (Exception)
            {
                document = null;
                return false;
            }
        }

        public static ModelStorageDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
                throw new FormatException("Storage document root must be a JSON object.");
            return new ModelStorageDocument
            {
                Directory = root.Get("directory").AsString(),
                Exists = root.Get("exists").AsBool(),
                Accessible = root.Get("accessible").AsBool(),
                Writable = root.Get("writable").AsBool(),
                Created = root.Get("created").AsBool(),
                Issue = root.Get("issue").AsString(),
                SearchPaths = root.Get("search_paths").AsStringList(),
                FreeBytes = root.Get("free_bytes").AsNullableLong(),
                TotalVolumeBytes = root.Get("total_volume_bytes").AsNullableLong(),
            };
        }
    }

    public sealed class ModelListDocument
    {
        public List<InstalledModelDocument> Models = new List<InstalledModelDocument>();
        public ModelStorageDocument Storage = new ModelStorageDocument();
        public bool OfflineMode;
        public string ActiveModelId;

        public static bool TryParse(string json, out ModelListDocument document)
        {
            try
            {
                document = Parse(json);
                return document != null;
            }
            catch (Exception)
            {
                document = null;
                return false;
            }
        }

        public static ModelListDocument Parse(string json)
        {
            return FromJsonNode(JsonNode.Parse(json));
        }

        public static ModelListDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
                throw new FormatException("Model list root must be a JSON object.");
            var models = new List<InstalledModelDocument>();
            foreach (var node in root.Get("models").AsArray())
            {
                if (node != null && node.IsObject)
                    models.Add(InstalledModelDocument.FromJsonNode(node));
            }

            var storageNode = root.Get("storage");
            return new ModelListDocument
            {
                Models = models,
                Storage = storageNode != null && storageNode.IsObject
                    ? ModelStorageDocument.FromJsonNode(storageNode)
                    : new ModelStorageDocument(),
                OfflineMode = root.Get("offline_mode").AsBool(),
                ActiveModelId = root.Get("active_model_id").AsString(),
            };
        }
    }

    public sealed class ModelDiskUsageDocument
    {
        public long TotalBytes;
        public List<KeyValuePair<string, long>> Models = new List<KeyValuePair<string, long>>();
        public long? FreeBytes;
        public long? VolumeTotalBytes;
        public string CalculatedAt;
        public bool Stale;

        public static bool TryParse(string json, out ModelDiskUsageDocument document)
        {
            try
            {
                var root = JsonNode.Parse(json);
                if (root == null || !root.IsObject)
                {
                    document = null;
                    return false;
                }

                var models = new List<KeyValuePair<string, long>>();
                foreach (var node in root.Get("models").AsArray())
                {
                    if (node == null || !node.IsObject)
                        continue;
                    var id = node.Get("id").AsString();
                    var size = node.Get("size_bytes").AsLong();
                    if (!string.IsNullOrWhiteSpace(id))
                        models.Add(new KeyValuePair<string, long>(id, size));
                }

                document = new ModelDiskUsageDocument
                {
                    TotalBytes = root.Get("total_bytes").AsLong(),
                    Models = models,
                    FreeBytes = root.Get("free_bytes").AsNullableLong(),
                    VolumeTotalBytes = root.Get("volume_total_bytes").AsNullableLong(),
                    CalculatedAt = root.Get("calculated_at").AsString(),
                    Stale = root.Get("stale").AsBool(),
                };
                return true;
            }
            catch (Exception)
            {
                document = null;
                return false;
            }
        }
    }

    public static class ModelInstallRequestJson
    {
        public static string HuggingFace(string identifier, string revision, string displayName)
        {
            var payload = new Dictionary<string, object>
            {
                { "source", "huggingface" },
                { "identifier", identifier ?? string.Empty },
            };
            if (!string.IsNullOrWhiteSpace(revision))
                payload["revision"] = revision;
            if (!string.IsNullOrWhiteSpace(displayName))
                payload["display_name"] = displayName;
            return JsonWriter.Serialize(payload, indented: false);
        }

        public static string LocalDirectory(string path, string identifier, string displayName)
        {
            var payload = new Dictionary<string, object>
            {
                { "source", "local_directory" },
                { "path", path ?? string.Empty },
            };
            if (!string.IsNullOrWhiteSpace(identifier))
                payload["identifier"] = identifier;
            if (!string.IsNullOrWhiteSpace(displayName))
                payload["display_name"] = displayName;
            return JsonWriter.Serialize(payload, indented: false);
        }
    }
}
