using System;
using NUnit.Framework;
using UnityAiAssets.Editor.Versioning;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class SchemaVersionTests
    {
        [Test]
        public void Parse_AcceptsMajorOnly()
        {
            var version = SchemaVersion.Parse("1");
            Assert.AreEqual(1, version.Major);
            Assert.AreEqual(0, version.Minor);
        }

        [Test]
        public void Parse_AcceptsMajorMinor()
        {
            var version = SchemaVersion.Parse("1.2");
            Assert.AreEqual(1, version.Major);
            Assert.AreEqual(2, version.Minor);
        }

        [Test]
        public void Parse_Rejects_EmptyOrNull()
        {
            Assert.Throws<FormatException>(() => SchemaVersion.Parse(""));
            Assert.Throws<FormatException>(() => SchemaVersion.Parse(null));
        }

        [Test]
        public void Parse_Rejects_Malformed()
        {
            Assert.Throws<FormatException>(() => SchemaVersion.Parse("abc"));
            Assert.Throws<FormatException>(() => SchemaVersion.Parse("1.2.3"));
            Assert.Throws<FormatException>(() => SchemaVersion.Parse("1."));
            Assert.Throws<FormatException>(() => SchemaVersion.Parse(".1"));
            Assert.Throws<FormatException>(() => SchemaVersion.Parse("-1"));
            Assert.Throws<FormatException>(() => SchemaVersion.Parse("1.-2"));
        }

        [Test]
        public void TryParse_ReturnsFalseForMalformed()
        {
            Assert.IsFalse(SchemaVersion.TryParse("not-a-version", out _));
        }

        [Test]
        public void Comparison_IsNumericNotLexicographic()
        {
            var v1_2 = SchemaVersion.Parse("1.2");
            var v1_10 = SchemaVersion.Parse("1.10");

            // Lexicographic string comparison would say "1.10" < "1.2" ("1" < "2"); numeric must not.
            Assert.IsTrue(v1_10 > v1_2);
            Assert.IsTrue(v1_2 < v1_10);
        }

        [Test]
        public void Comparison_MajorTakesPrecedenceOverMinor()
        {
            var v2_0 = SchemaVersion.Parse("2.0");
            var v1_99 = SchemaVersion.Parse("1.99");
            Assert.IsTrue(v2_0 > v1_99);
        }

        [Test]
        public void Equality_ComparesMajorAndMinor()
        {
            Assert.AreEqual(SchemaVersion.Parse("1.0"), SchemaVersion.Parse("1"));
            Assert.AreNotEqual(SchemaVersion.Parse("1.1"), SchemaVersion.Parse("1.0"));
        }

        [Test]
        public void HasSameMajor_MatchesOnlyMajor()
        {
            var version = SchemaVersion.Parse("1.5");
            Assert.IsTrue(version.HasSameMajor(1));
            Assert.IsFalse(version.HasSameMajor(2));
        }

        [Test]
        public void ToString_RoundTripsMajorDotMinor()
        {
            Assert.AreEqual("1.0", SchemaVersion.Parse("1").ToString());
            Assert.AreEqual("3.7", SchemaVersion.Parse("3.7").ToString());
        }

        [Test]
        public void PackageSupportsManifest11ByMajor()
        {
            Assert.AreEqual("0.8.0", ClientCompatibility.PackageVersion);
            Assert.IsTrue(SchemaVersion.Parse("1.1").HasSameMajor(ClientCompatibility.SupportedManifestSchemaMajor));
        }
    }
}
