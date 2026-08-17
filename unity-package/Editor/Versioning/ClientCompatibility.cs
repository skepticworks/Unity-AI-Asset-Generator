namespace UnityAiAssets.Editor.Versioning
{
    /// <summary>
    /// Single source of truth for what this package version understands.
    /// Bump alongside deliberate, tested support for a new major version.
    /// </summary>
    public static class ClientCompatibility
    {
        public const int SupportedApiMajor = 1;
        public const int SupportedCapabilitiesSchemaMajor = 1;
        public const int SupportedManifestSchemaMajor = 1;
        public const string PackageVersion = "0.11.0";
    }
}
