namespace UnityAiAssets.Editor.Generation
{
    public enum GenerationState
    {
        Idle = 0,
        CheckingConnection = 1,
        Submitting = 2,
        Generating = 3,
        Downloading = 4,
        Importing = 5,
        Completed = 6,
        Failed = 7,
        Cancelled = 8,
        RefreshingCapabilities = 9
    }
}
