namespace UnityAiAssets.Editor.Profiles
{
    public static class ProfileSchemaVersions
    {
        public const string GenerationProfile = "1.1";
        public const string PromptTemplate = "1.0";
        public const string NegativePrompt = "1.0";
        public const string GenerationProfileSchemaName = "generation-profile";
        public const string PromptTemplateSchemaName = "prompt-template";
        public const string NegativePromptSchemaName = "negative-prompt-profile";
    }

    public static class ProfileErrorCodes
    {
        public const string InvalidJson = "PROFILE_INVALID_JSON";
        public const string FileTooLarge = "PROFILE_FILE_TOO_LARGE";
        public const string SchemaInvalid = "PROFILE_SCHEMA_INVALID";
        public const string SchemaUnsupported = "PROFILE_SCHEMA_UNSUPPORTED";
        public const string DuplicateId = "PROFILE_DUPLICATE_ID";
        public const string BuiltinCollision = "PROFILE_BUILTIN_COLLISION";
        public const string ReferenceMissing = "PROFILE_REFERENCE_MISSING";
        public const string AssetTypeUnknown = "PROFILE_ASSET_TYPE_UNKNOWN";
        public const string Incompatible = "PROFILE_INCOMPATIBLE";
        public const string ReadOnly = "PROFILE_BUILTIN_READ_ONLY";
        public const string NotFound = "PROFILE_NOT_FOUND";
        public const string OverwriteRefused = "PROFILE_OVERWRITE_REFUSED";
        public const string FieldRequired = "FIELD_REQUIRED";
        public const string ValueInvalid = "VALUE_INVALID";
        public const string ValueTooLong = "VALUE_TOO_LONG";
        public const string ValueOutOfRange = "VALUE_OUT_OF_RANGE";
        public const string ProfileIdInvalid = "PROFILE_ID_INVALID";
        public const string ProfileIdDuplicate = "PROFILE_ID_DUPLICATE";
        public const string BuiltinImmutable = "PROFILE_BUILTIN_IMMUTABLE";
        public const string ReferenceInvalid = "PROFILE_REFERENCE_INVALID";
        public const string TemplateNotFound = "PROFILE_TEMPLATE_NOT_FOUND";
        public const string NegativeProfileNotFound = "PROFILE_NEGATIVE_PROFILE_NOT_FOUND";
        public const string ImportProfileNotFound = "PROFILE_IMPORT_PROFILE_NOT_FOUND";
        public const string SerializationFailed = "PROFILE_SERIALIZATION_FAILED";
        public const string PersistenceFailed = "PROFILE_PERSISTENCE_FAILED";
        public const string MigrationRequired = "PROFILE_MIGRATION_REQUIRED";
        public const string MigrationFailed = "PROFILE_MIGRATION_FAILED";
        public const string ImportFailed = "PROFILE_IMPORT_FAILED";
        public const string ExportFailed = "PROFILE_EXPORT_FAILED";
        public const string Conflict = "PROFILE_CONFLICT";
    }

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
        public const string BackgroundRemovalUnavailable = "BACKGROUND_REMOVAL_UNAVAILABLE";
        public const string PixelsPerUnitInvalid = "PIXELS_PER_UNIT_INVALID";
        public const string PivotModeInvalid = "PIVOT_MODE_INVALID";
        public const string CustomPivotInvalid = "CUSTOM_PIVOT_INVALID";
    }
}
