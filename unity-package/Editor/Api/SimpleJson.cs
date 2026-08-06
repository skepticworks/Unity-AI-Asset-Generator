using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace UnityAiAssets.Editor.Api
{
    public enum JsonNodeKind
    {
        Null,
        Bool,
        Number,
        String,
        Array,
        Object
    }

    /// <summary>
    /// Minimal recursive-descent JSON parser producing a typed node tree.
    /// Unity's JsonUtility cannot deserialize string arrays nested inside
    /// classes or dictionaries reliably, so nested/variable-shape payloads
    /// (capabilities, error envelopes, manifests) are parsed with this
    /// instead of JsonUtility.
    /// </summary>
    public sealed class JsonNode
    {
        public static readonly JsonNode Null = new JsonNode(JsonNodeKind.Null);

        readonly JsonNodeKind _kind;
        readonly bool _boolValue;
        readonly double _numberValue;
        readonly string _stringValue;
        readonly List<JsonNode> _arrayValue;
        readonly Dictionary<string, JsonNode> _objectValue;

        JsonNode(JsonNodeKind kind)
        {
            _kind = kind;
        }

        JsonNode(bool value) : this(JsonNodeKind.Bool)
        {
            _boolValue = value;
        }

        JsonNode(double value) : this(JsonNodeKind.Number)
        {
            _numberValue = value;
        }

        JsonNode(string value) : this(JsonNodeKind.String)
        {
            _stringValue = value;
        }

        JsonNode(List<JsonNode> value) : this(JsonNodeKind.Array)
        {
            _arrayValue = value;
        }

        JsonNode(Dictionary<string, JsonNode> value) : this(JsonNodeKind.Object)
        {
            _objectValue = value;
        }

        public JsonNodeKind Kind => _kind;
        public bool IsNull => _kind == JsonNodeKind.Null;
        public bool IsObject => _kind == JsonNodeKind.Object;
        public bool IsArray => _kind == JsonNodeKind.Array;

        public static JsonNode Parse(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                throw new FormatException("JSON payload is empty.");
            }

            var parser = new Parser(json);
            var node = parser.ParseValue();
            parser.SkipWhitespace();
            if (!parser.AtEnd)
            {
                throw new FormatException("Unexpected trailing content after JSON value.");
            }

            return node;
        }

        public static bool TryParse(string json, out JsonNode node)
        {
            try
            {
                node = Parse(json);
                return true;
            }
            catch (Exception)
            {
                node = null;
                return false;
            }
        }

        public JsonNode this[string key] => Get(key);

        public JsonNode Get(string key)
        {
            if (_kind != JsonNodeKind.Object || _objectValue == null)
            {
                return Null;
            }

            return _objectValue.TryGetValue(key, out var value) ? value : Null;
        }

        public bool HasKey(string key)
        {
            return _kind == JsonNodeKind.Object && _objectValue != null && _objectValue.ContainsKey(key);
        }

        public IReadOnlyDictionary<string, JsonNode> AsObject()
        {
            return _objectValue ?? EmptyObject;
        }

        public IReadOnlyList<JsonNode> AsArray()
        {
            return _arrayValue ?? EmptyArray;
        }

        public string AsString(string fallback = null)
        {
            return _kind == JsonNodeKind.String ? _stringValue : fallback;
        }

        public bool AsBool(bool fallback = false)
        {
            return _kind == JsonNodeKind.Bool ? _boolValue : fallback;
        }

        public double AsDouble(double fallback = 0d)
        {
            return _kind == JsonNodeKind.Number ? _numberValue : fallback;
        }

        public int AsInt(int fallback = 0)
        {
            return _kind == JsonNodeKind.Number ? (int)_numberValue : fallback;
        }

        public long AsLong(long fallback = 0)
        {
            return _kind == JsonNodeKind.Number ? (long)_numberValue : fallback;
        }

        public float AsFloat(float fallback = 0f)
        {
            return _kind == JsonNodeKind.Number ? (float)_numberValue : fallback;
        }

        public List<string> AsStringList()
        {
            var result = new List<string>();
            if (_kind != JsonNodeKind.Array || _arrayValue == null)
            {
                return result;
            }

            foreach (var item in _arrayValue)
            {
                if (item.Kind == JsonNodeKind.String)
                {
                    result.Add(item.AsString());
                }
            }

            return result;
        }

        static readonly Dictionary<string, JsonNode> EmptyObject = new Dictionary<string, JsonNode>();
        static readonly List<JsonNode> EmptyArray = new List<JsonNode>();

        sealed class Parser
        {
            readonly string _text;
            int _pos;

            public Parser(string text)
            {
                _text = text;
                _pos = 0;
            }

            public bool AtEnd => _pos >= _text.Length;

            public JsonNode ParseValue()
            {
                SkipWhitespace();
                if (AtEnd)
                {
                    throw new FormatException("Unexpected end of JSON input.");
                }

                var c = _text[_pos];
                switch (c)
                {
                    case '{':
                        return ParseObject();
                    case '[':
                        return ParseArray();
                    case '"':
                        return new JsonNode(ParseString());
                    case 't':
                    case 'f':
                        return ParseBool();
                    case 'n':
                        ParseLiteral("null");
                        return JsonNode.Null;
                    default:
                        return ParseNumber();
                }
            }

            JsonNode ParseObject()
            {
                Expect('{');
                var dict = new Dictionary<string, JsonNode>();
                SkipWhitespace();
                if (Peek() == '}')
                {
                    _pos++;
                    return new JsonNode(dict);
                }

                while (true)
                {
                    SkipWhitespace();
                    var key = ParseString();
                    SkipWhitespace();
                    Expect(':');
                    var value = ParseValue();
                    dict[key] = value;
                    SkipWhitespace();
                    var next = Peek();
                    if (next == ',')
                    {
                        _pos++;
                        continue;
                    }

                    if (next == '}')
                    {
                        _pos++;
                        break;
                    }

                    throw new FormatException($"Expected ',' or '}}' at position {_pos}.");
                }

                return new JsonNode(dict);
            }

            JsonNode ParseArray()
            {
                Expect('[');
                var list = new List<JsonNode>();
                SkipWhitespace();
                if (Peek() == ']')
                {
                    _pos++;
                    return new JsonNode(list);
                }

                while (true)
                {
                    var value = ParseValue();
                    list.Add(value);
                    SkipWhitespace();
                    var next = Peek();
                    if (next == ',')
                    {
                        _pos++;
                        continue;
                    }

                    if (next == ']')
                    {
                        _pos++;
                        break;
                    }

                    throw new FormatException($"Expected ',' or ']' at position {_pos}.");
                }

                return new JsonNode(list);
            }

            string ParseString()
            {
                Expect('"');
                var sb = new StringBuilder();
                while (true)
                {
                    if (AtEnd)
                    {
                        throw new FormatException("Unterminated JSON string.");
                    }

                    var c = _text[_pos++];
                    if (c == '"')
                    {
                        break;
                    }

                    if (c == '\\')
                    {
                        if (AtEnd)
                        {
                            throw new FormatException("Unterminated JSON escape sequence.");
                        }

                        var esc = _text[_pos++];
                        switch (esc)
                        {
                            case '"': sb.Append('"'); break;
                            case '\\': sb.Append('\\'); break;
                            case '/': sb.Append('/'); break;
                            case 'b': sb.Append('\b'); break;
                            case 'f': sb.Append('\f'); break;
                            case 'n': sb.Append('\n'); break;
                            case 'r': sb.Append('\r'); break;
                            case 't': sb.Append('\t'); break;
                            case 'u':
                                if (_pos + 4 > _text.Length)
                                {
                                    throw new FormatException("Invalid unicode escape sequence.");
                                }

                                var hex = _text.Substring(_pos, 4);
                                _pos += 4;
                                sb.Append((char)ushort.Parse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture));
                                break;
                            default:
                                throw new FormatException($"Invalid escape character '\\{esc}'.");
                        }
                    }
                    else
                    {
                        sb.Append(c);
                    }
                }

                return sb.ToString();
            }

            JsonNode ParseNumber()
            {
                var start = _pos;
                if (Peek() == '-')
                {
                    _pos++;
                }

                while (!AtEnd && char.IsDigit(_text[_pos]))
                {
                    _pos++;
                }

                if (!AtEnd && _text[_pos] == '.')
                {
                    _pos++;
                    while (!AtEnd && char.IsDigit(_text[_pos]))
                    {
                        _pos++;
                    }
                }

                if (!AtEnd && (_text[_pos] == 'e' || _text[_pos] == 'E'))
                {
                    _pos++;
                    if (!AtEnd && (_text[_pos] == '+' || _text[_pos] == '-'))
                    {
                        _pos++;
                    }

                    while (!AtEnd && char.IsDigit(_text[_pos]))
                    {
                        _pos++;
                    }
                }

                if (_pos == start)
                {
                    throw new FormatException($"Invalid JSON number at position {_pos}.");
                }

                var slice = _text.Substring(start, _pos - start);
                if (!double.TryParse(slice, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
                {
                    throw new FormatException($"Invalid JSON number '{slice}'.");
                }

                return new JsonNode(value);
            }

            JsonNode ParseBool()
            {
                if (Peek() == 't')
                {
                    ParseLiteral("true");
                    return new JsonNode(true);
                }

                ParseLiteral("false");
                return new JsonNode(false);
            }

            void ParseLiteral(string literal)
            {
                if (_pos + literal.Length > _text.Length ||
                    string.CompareOrdinal(_text, _pos, literal, 0, literal.Length) != 0)
                {
                    throw new FormatException($"Expected literal '{literal}' at position {_pos}.");
                }

                _pos += literal.Length;
            }

            char Peek() => AtEnd ? '\0' : _text[_pos];

            void Expect(char expected)
            {
                SkipWhitespace();
                if (AtEnd || _text[_pos] != expected)
                {
                    throw new FormatException($"Expected '{expected}' at position {_pos}.");
                }

                _pos++;
            }

            public void SkipWhitespace()
            {
                while (!AtEnd && char.IsWhiteSpace(_text[_pos]))
                {
                    _pos++;
                }
            }
        }
    }
}
