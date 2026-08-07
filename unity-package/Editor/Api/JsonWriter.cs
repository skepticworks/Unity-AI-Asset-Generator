using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

namespace UnityAiAssets.Editor.Api
{
    /// <summary>Small deterministic JSON serializer for profile files.</summary>
    public static class JsonWriter
    {
        public static string Serialize(object value, bool indented = true)
        {
            var builder = new StringBuilder();
            Write(builder, value, indented, 0);
            if (indented) builder.Append('\n');
            return builder.ToString();
        }

        static void Write(StringBuilder builder, object value, bool indented, int depth)
        {
            if (value == null) { builder.Append("null"); return; }
            if (value is string text) { WriteString(builder, text); return; }
            if (value is bool boolean) { builder.Append(boolean ? "true" : "false"); return; }
            if (value is Enum) { WriteString(builder, value.ToString()); return; }
            if (value is IDictionary dictionary) { WriteObject(builder, dictionary, indented, depth); return; }
            if (value is IEnumerable sequence) { WriteArray(builder, sequence, indented, depth); return; }
            if (value is IFormattable formattable)
            {
                builder.Append(formattable.ToString(null, CultureInfo.InvariantCulture));
                return;
            }
            throw new ArgumentException("Unsupported JSON value type: " + value.GetType().FullName);
        }

        static void WriteObject(StringBuilder builder, IDictionary values, bool indented, int depth)
        {
            builder.Append('{');
            var entries = values.Keys.Cast<object>()
                .Select(key => new KeyValuePair<string, object>(Convert.ToString(key, CultureInfo.InvariantCulture), values[key]))
                .OrderBy(pair => pair.Key, StringComparer.Ordinal).ToList();
            for (var i = 0; i < entries.Count; i++)
            {
                if (i > 0) builder.Append(',');
                NewLine(builder, indented, depth + 1);
                WriteString(builder, entries[i].Key);
                builder.Append(indented ? ": " : ":");
                Write(builder, entries[i].Value, indented, depth + 1);
            }
            if (entries.Count > 0) NewLine(builder, indented, depth);
            builder.Append('}');
        }

        static void WriteArray(StringBuilder builder, IEnumerable values, bool indented, int depth)
        {
            builder.Append('[');
            var items = values.Cast<object>().ToList();
            for (var i = 0; i < items.Count; i++)
            {
                if (i > 0) builder.Append(',');
                NewLine(builder, indented, depth + 1);
                Write(builder, items[i], indented, depth + 1);
            }
            if (items.Count > 0) NewLine(builder, indented, depth);
            builder.Append(']');
        }

        static void NewLine(StringBuilder builder, bool indented, int depth)
        {
            if (!indented) return;
            builder.Append('\n').Append(' ', depth * 2);
        }

        static void WriteString(StringBuilder builder, string value)
        {
            builder.Append('"');
            foreach (var c in value ?? string.Empty)
            {
                switch (c)
                {
                    case '"': builder.Append("\\\""); break;
                    case '\\': builder.Append("\\\\"); break;
                    case '\b': builder.Append("\\b"); break;
                    case '\f': builder.Append("\\f"); break;
                    case '\n': builder.Append("\\n"); break;
                    case '\r': builder.Append("\\r"); break;
                    case '\t': builder.Append("\\t"); break;
                    default:
                        if (c < 32) builder.Append("\\u").Append(((int)c).ToString("x4"));
                        else builder.Append(c);
                        break;
                }
            }
            builder.Append('"');
        }
    }
}
