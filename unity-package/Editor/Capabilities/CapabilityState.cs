namespace UnityAiAssets.Editor.Capabilities
{
    /// <summary>
    /// Lifecycle state of a cached capability document for a given backend base URL.
    /// </summary>
    public enum CapabilityState
    {
        /// <summary>Never fetched for this backend URL.</summary>
        Unknown = 0,

        /// <summary>A fetch is currently in flight.</summary>
        Loading = 1,

        /// <summary>Fetched successfully and compatible with this package.</summary>
        Ready = 2,

        /// <summary>Previously fetched successfully, but a subsequent refresh failed; the
        /// cached document may no longer reflect the backend's actual state.</summary>
        Stale = 3,

        /// <summary>The backend could not be reached or returned an error.</summary>
        Unavailable = 4,

        /// <summary>The backend responded but its API/schema versions are unsupported.</summary>
        Incompatible = 5
    }
}
