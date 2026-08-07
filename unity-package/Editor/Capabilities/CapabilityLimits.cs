namespace UnityAiAssets.Editor.Capabilities
{
    /// <summary>Shared pure checks for capability-constrained generation values.</summary>
    public static class CapabilityLimits
    {
        public static bool IsInRange(int value, int minimum, int maximum) =>
            value >= minimum && value <= maximum;

        public static bool IsInRange(long value, long minimum, long maximum) =>
            value >= minimum && value <= maximum;

        public static bool IsInRange(float value, float minimum, float maximum) =>
            value >= minimum && value <= maximum;

        public static bool IsMultiple(int value, int multiple) =>
            multiple <= 1 || value % multiple == 0;
    }
}
