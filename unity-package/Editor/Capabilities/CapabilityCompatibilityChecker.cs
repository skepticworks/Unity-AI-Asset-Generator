using System.Collections.Generic;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Versioning;

namespace UnityAiAssets.Editor.Capabilities
{
    /// <summary>
    /// Result of checking a capability document against what this package understands.
    /// </summary>
    public sealed class CapabilityCompatibilityResult
    {
        public bool IsCompatible => Reasons.Count == 0;

        public List<string> Reasons { get; } = new List<string>();
    }

    /// <summary>
    /// This package supports public API major 1, capability schema major 1, and manifest
    /// schema major 1. Higher minor versions are always accepted (additive/backward-compatible
    /// by contract); a higher major version is treated as incompatible.
    /// </summary>
    public static class CapabilityCompatibilityChecker
    {
        public static CapabilityCompatibilityResult Check(CapabilityDocument document)
        {
            var result = new CapabilityCompatibilityResult();
            if (document == null)
            {
                result.Reasons.Add("No capability document was provided.");
                return result;
            }

            if (document.Api == null || document.Api.Major != ClientCompatibility.SupportedApiMajor)
            {
                var actual = document.Api?.Major.ToString() ?? "unknown";
                result.Reasons.Add(
                    $"Backend API major version {actual} is not supported by this package " +
                    $"(supports major {ClientCompatibility.SupportedApiMajor}).");
            }

            if (!TryCheckSchemaMajor(
                    document.Schemas?.Capabilities,
                    ClientCompatibility.SupportedCapabilitiesSchemaMajor,
                    "capabilities",
                    out var capabilitiesReason))
            {
                result.Reasons.Add(capabilitiesReason);
            }

            if (!TryCheckSchemaMajor(
                    document.Schemas?.GenerationManifest,
                    ClientCompatibility.SupportedManifestSchemaMajor,
                    "generation_manifest",
                    out var manifestReason))
            {
                result.Reasons.Add(manifestReason);
            }

            return result;
        }

        public static bool IsApiMajorSupported(int major) => major == ClientCompatibility.SupportedApiMajor;

        public static bool IsCapabilitiesSchemaSupported(SchemaVersion version) =>
            version.HasSameMajor(ClientCompatibility.SupportedCapabilitiesSchemaMajor);

        public static bool IsManifestSchemaSupported(SchemaVersion version) =>
            version.HasSameMajor(ClientCompatibility.SupportedManifestSchemaMajor);

        static bool TryCheckSchemaMajor(string rawVersion, int supportedMajor, string schemaName, out string reason)
        {
            if (!SchemaVersion.TryParse(rawVersion, out var version))
            {
                reason = $"Backend '{schemaName}' schema version '{rawVersion}' could not be parsed.";
                return false;
            }

            if (!version.HasSameMajor(supportedMajor))
            {
                reason =
                    $"Backend '{schemaName}' schema major version {version.Major} is not supported by this " +
                    $"package (supports major {supportedMajor}).";
                return false;
            }

            reason = null;
            return true;
        }
    }
}
