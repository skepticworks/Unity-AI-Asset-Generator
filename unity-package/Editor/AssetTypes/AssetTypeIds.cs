using System;
using System.Collections.Generic;

namespace UnityAiAssets.Editor.AssetTypes
{
    public static class AssetTypeIds
    {
        public const string Texture = "texture";
        public const string Sprite = "sprite";
        public const string Icon = "icon";
        public const string Ui = "ui";

        public static readonly IReadOnlyCollection<string> Known =
            new[] { Texture, Sprite, Icon, Ui };

        public static bool IsKnown(string value)
        {
            foreach (var id in Known)
                if (string.Equals(id, value, StringComparison.Ordinal)) return true;
            return false;
        }
    }
}
