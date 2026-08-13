using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Importing
{
    /// <summary>
    /// Remembers imported generation IDs so a UI refresh cannot reimport the same result.
    /// </summary>
    public sealed class ImportedGenerationRegistry
    {
        readonly HashSet<string> _ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        readonly string _path;

        public ImportedGenerationRegistry(string persistencePath)
        {
            if (string.IsNullOrWhiteSpace(persistencePath))
                throw new ArgumentException("Persistence path is required.", nameof(persistencePath));
            _path = persistencePath;
            Load();
        }

        public IReadOnlyCollection<string> ImportedIds => _ids;

        public int Count => _ids.Count;

        public bool IsImported(string generationId)
        {
            return !string.IsNullOrWhiteSpace(generationId) && _ids.Contains(generationId.Trim());
        }

        public bool MarkImported(string generationId)
        {
            if (string.IsNullOrWhiteSpace(generationId))
                return false;
            var id = generationId.Trim();
            if (!_ids.Add(id))
                return false;
            Save();
            return true;
        }

        public IEnumerable<string> FilterNew(IEnumerable<string> generationIds)
        {
            foreach (var id in generationIds)
            {
                if (!IsImported(id))
                    yield return id;
            }
        }

        void Load()
        {
            _ids.Clear();
            if (!File.Exists(_path))
                return;
            try
            {
                var json = File.ReadAllText(_path, Encoding.UTF8);
                var root = JsonNode.Parse(json);
                var list = root.Get("generation_ids");
                if (list == null || !list.IsArray)
                    return;
                foreach (var item in list.AsArray())
                {
                    var value = item.AsString();
                    if (!string.IsNullOrWhiteSpace(value))
                        _ids.Add(value.Trim());
                }
            }
            catch (Exception)
            {
                _ids.Clear();
            }
        }

        void Save()
        {
            var directory = Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(directory))
                Directory.CreateDirectory(directory);

            var sb = new StringBuilder();
            sb.Append("{\"generation_ids\":[");
            var first = true;
            foreach (var id in _ids)
            {
                if (!first)
                    sb.Append(',');
                first = false;
                sb.Append('"').Append(id.Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"');
            }

            sb.Append("]}");
            var tmp = _path + ".tmp";
            File.WriteAllText(tmp, sb.ToString(), Encoding.UTF8);
            if (File.Exists(_path))
                File.Delete(_path);
            File.Move(tmp, _path);
        }
    }
}
