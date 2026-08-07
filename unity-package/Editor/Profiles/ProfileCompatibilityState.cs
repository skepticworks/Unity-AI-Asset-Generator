namespace UnityAiAssets.Editor.Profiles
{
    public enum ProfileCompatibilityState
    {
        Compatible,
        Incompatible,
        PartiallySupported,
        Unknown
    }

    public static class CompatibilityReasonCodes
    {
        public const string CapabilitiesUnavailable = "CAPABILITIES_UNAVAILABLE";
        public const string OperationUnsupported = "OPERATION_UNSUPPORTED";
        public const string AssetTypeUnsupported = "ASSET_TYPE_UNSUPPORTED";
        public const string WidthOutOfRange = "WIDTH_OUT_OF_RANGE";
        public const string HeightOutOfRange = "HEIGHT_OUT_OF_RANGE";
        public const string StepsOutOfRange = "STEPS_OUT_OF_RANGE";
        public const string GuidanceOutOfRange = "GUIDANCE_OUT_OF_RANGE";
        public const string NegativePromptUnsupported = "NEGATIVE_PROMPT_UNSUPPORTED";
        public const string WidthMultipleInvalid = "WIDTH_MULTIPLE_INVALID";
        public const string HeightMultipleInvalid = "HEIGHT_MULTIPLE_INVALID";
        public const string ImportProfileUnknown = "IMPORT_PROFILE_UNKNOWN";
        public const string TemplateUnknown = "TEMPLATE_UNKNOWN";
        public const string NegativeProfileUnknown = "NEGATIVE_PROFILE_UNKNOWN";
        public const string SchemaVersionUnsupported = "SCHEMA_VERSION_UNSUPPORTED";
        public const string SeedOutOfRange = "SEED_OUT_OF_RANGE";
        public const string PromptTooLong = "PROMPT_TOO_LONG";
        public const string NegativePromptTooLong = "NEGATIVE_PROMPT_TOO_LONG";
    }
}
