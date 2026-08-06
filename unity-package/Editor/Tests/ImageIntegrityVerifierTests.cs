using System.Text;
using NUnit.Framework;
using UnityAiAssets.Editor.Integrity;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ImageIntegrityVerifierTests
    {
        static readonly byte[] SampleBytes = Encoding.UTF8.GetBytes("unity-ai-assets-integrity-fixture");

        [Test]
        public void ComputeSha256Hex_IsDeterministic()
        {
            var first = ImageIntegrityVerifier.ComputeSha256Hex(SampleBytes);
            var second = ImageIntegrityVerifier.ComputeSha256Hex(SampleBytes);
            Assert.AreEqual(first, second);
            Assert.AreEqual(64, first.Length);
        }

        [Test]
        public void Verify_SucceedsWhenHashAndSizeMatch()
        {
            var hash = ImageIntegrityVerifier.ComputeSha256Hex(SampleBytes);
            var result = ImageIntegrityVerifier.Verify(SampleBytes, hash, SampleBytes.Length);
            Assert.IsTrue(result.IsValid);
            Assert.AreEqual(hash, result.ActualSha256);
            Assert.AreEqual(SampleBytes.Length, result.ActualByteSize);
        }

        [Test]
        public void Verify_SucceedsWhenNoExpectationsProvided()
        {
            var result = ImageIntegrityVerifier.Verify(SampleBytes, null, null);
            Assert.IsTrue(result.IsValid);
        }

        [Test]
        public void Verify_FailsOnHashMismatch()
        {
            var result = ImageIntegrityVerifier.Verify(
                SampleBytes,
                "0000000000000000000000000000000000000000000000000000000000000000",
                null);
            Assert.IsFalse(result.IsValid);
            StringAssert.Contains("SHA256 mismatch", result.FailureReason);
        }

        [Test]
        public void Verify_FailsOnByteSizeMismatch()
        {
            var result = ImageIntegrityVerifier.Verify(SampleBytes, null, SampleBytes.Length + 1);
            Assert.IsFalse(result.IsValid);
            StringAssert.Contains("Byte size mismatch", result.FailureReason);
        }

        [Test]
        public void Verify_FailsOnEmptyBytes()
        {
            var result = ImageIntegrityVerifier.Verify(new byte[0], null, null);
            Assert.IsFalse(result.IsValid);
        }

        [Test]
        public void Verify_FailsOnInvalidHashFormat()
        {
            var result = ImageIntegrityVerifier.Verify(SampleBytes, "not-a-sha256", SampleBytes.Length);
            Assert.IsFalse(result.IsValid);
            StringAssert.Contains("Invalid manifest hash format", result.FailureReason);
        }

        [Test]
        public void IsValidSha256Hex_RejectsWrongLength()
        {
            Assert.IsFalse(ImageIntegrityVerifier.IsValidSha256Hex("abcd"));
            Assert.IsFalse(ImageIntegrityVerifier.IsValidSha256Hex(new string('g', 64)));
        }

        [Test]
        public void Verify_HashComparisonIsCaseInsensitive()
        {
            var hash = ImageIntegrityVerifier.ComputeSha256Hex(SampleBytes).ToUpperInvariant();
            var result = ImageIntegrityVerifier.Verify(SampleBytes, hash, null);
            Assert.IsTrue(result.IsValid);
        }
    }
}
