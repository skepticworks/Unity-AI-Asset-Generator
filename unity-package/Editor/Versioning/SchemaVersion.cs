using System;
using System.Globalization;

namespace UnityAiAssets.Editor.Versioning
{
    /// <summary>
    /// A "major[.minor]" schema/API version, e.g. "1", "1.0", "1.2".
    /// Comparisons are numeric on major/minor, never lexicographic
    /// (so "1.10" is greater than "1.2").
    /// </summary>
    public readonly struct SchemaVersion : IEquatable<SchemaVersion>, IComparable<SchemaVersion>
    {
        public int Major { get; }
        public int Minor { get; }

        public SchemaVersion(int major, int minor)
        {
            if (major < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(major), "Major version must be non-negative.");
            }

            if (minor < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(minor), "Minor version must be non-negative.");
            }

            Major = major;
            Minor = minor;
        }

        public static SchemaVersion Parse(string value)
        {
            if (!TryParse(value, out var version))
            {
                throw new FormatException($"'{value}' is not a valid schema version (expected 'major' or 'major.minor').");
            }

            return version;
        }

        public static bool TryParse(string value, out SchemaVersion version)
        {
            version = default;
            if (string.IsNullOrWhiteSpace(value))
            {
                return false;
            }

            var trimmed = value.Trim();
            var parts = trimmed.Split('.');
            if (parts.Length < 1 || parts.Length > 2)
            {
                return false;
            }

            if (!TryParseNonNegativeInt(parts[0], out var major))
            {
                return false;
            }

            var minor = 0;
            if (parts.Length == 2 && !TryParseNonNegativeInt(parts[1], out minor))
            {
                return false;
            }

            version = new SchemaVersion(major, minor);
            return true;
        }

        static bool TryParseNonNegativeInt(string text, out int value)
        {
            value = 0;
            if (string.IsNullOrEmpty(text))
            {
                return false;
            }

            foreach (var c in text)
            {
                if (!char.IsDigit(c))
                {
                    return false;
                }
            }

            return int.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out value);
        }

        public bool HasSameMajor(int major) => Major == major;

        public bool IsCompatibleWith(SchemaVersion supported)
        {
            // Same major is required; a higher minor than what we know about is fine
            // because minor bumps must be additive/backward-compatible.
            return Major == supported.Major;
        }

        public int CompareTo(SchemaVersion other)
        {
            var majorCompare = Major.CompareTo(other.Major);
            return majorCompare != 0 ? majorCompare : Minor.CompareTo(other.Minor);
        }

        public bool Equals(SchemaVersion other) => Major == other.Major && Minor == other.Minor;

        public override bool Equals(object obj) => obj is SchemaVersion other && Equals(other);

        public override int GetHashCode() => (Major * 397) ^ Minor;

        public override string ToString() => $"{Major}.{Minor}";

        public static bool operator ==(SchemaVersion left, SchemaVersion right) => left.Equals(right);

        public static bool operator !=(SchemaVersion left, SchemaVersion right) => !left.Equals(right);

        public static bool operator <(SchemaVersion left, SchemaVersion right) => left.CompareTo(right) < 0;

        public static bool operator >(SchemaVersion left, SchemaVersion right) => left.CompareTo(right) > 0;

        public static bool operator <=(SchemaVersion left, SchemaVersion right) => left.CompareTo(right) <= 0;

        public static bool operator >=(SchemaVersion left, SchemaVersion right) => left.CompareTo(right) >= 0;
    }
}
