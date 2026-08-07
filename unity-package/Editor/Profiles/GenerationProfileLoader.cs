using System;
using System.IO;
using System.Text;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Profiles
{
    public static class GenerationProfileLoader
    {
        public const int MaximumBytes = 256000;

        public static GenerationProfileParseResult Load(string path)
        {
            var info = new FileInfo(path);
            if (!info.Exists) throw new FileNotFoundException("Profile file not found.", path);
            if (info.Length > MaximumBytes)
                return Failed(ProfileErrorCodes.FileTooLarge, "Profile exceeds 256KB.");
            try
            {
                var bytes = File.ReadAllBytes(path);
                var utf8 = new UTF8Encoding(false, true);
                return GenerationProfileSchema.Parse(JsonNode.Parse(utf8.GetString(bytes)), path);
            }
            catch (Exception exception)
            {
                return Failed(ProfileErrorCodes.InvalidJson, exception.Message);
            }
        }

        public static bool IsCandidate(string path)
        {
            var name = Path.GetFileName(path);
            return path.EndsWith(".json", StringComparison.OrdinalIgnoreCase) &&
                   !name.EndsWith(".bak", StringComparison.OrdinalIgnoreCase) &&
                   !name.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase) &&
                   !name.Contains(".~");
        }

        static GenerationProfileParseResult Failed(string code, string message)
        {
            var result = new GenerationProfileParseResult();
            result.Issues.Add(new ValidationIssue { Path = "$", Code = code, Message = message });
            return result;
        }
    }
}
