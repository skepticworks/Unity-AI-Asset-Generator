using System;
using System.Security.Cryptography;
using System.Text;

namespace UnityAiAssets.Editor.Integrity
{
    /// <summary>
    /// Result of checking downloaded bytes against a manifest's declared SHA256/byte size.
    /// </summary>
    public sealed class IntegrityResult
    {
        public bool IsValid;
        public string ActualSha256;
        public long ActualByteSize;
        public string FailureReason;

        public static IntegrityResult Success(string actualSha256, long actualByteSize)
        {
            return new IntegrityResult
            {
                IsValid = true,
                ActualSha256 = actualSha256,
                ActualByteSize = actualByteSize,
            };
        }

        public static IntegrityResult Failure(string actualSha256, long actualByteSize, string reason)
        {
            return new IntegrityResult
            {
                IsValid = false,
                ActualSha256 = actualSha256,
                ActualByteSize = actualByteSize,
                FailureReason = reason,
            };
        }
    }

    /// <summary>
    /// Verifies downloaded image bytes against the SHA256 hash and byte size recorded in a
    /// generation manifest, before the bytes are ever written into the Unity project.
    /// </summary>
    public static class ImageIntegrityVerifier
    {
        public static string ComputeSha256Hex(byte[] bytes)
        {
            if (bytes == null)
            {
                throw new ArgumentNullException(nameof(bytes));
            }

            using var sha256 = SHA256.Create();
            var hash = sha256.ComputeHash(bytes);
            var sb = new StringBuilder(hash.Length * 2);
            foreach (var b in hash)
            {
                sb.Append(b.ToString("x2"));
            }

            return sb.ToString();
        }

        /// <summary>
        /// Verifies <paramref name="bytes"/> against an expected hex-encoded SHA256 digest and
        /// an expected byte size. Either expectation may be omitted (null/empty) when the
        /// manifest does not provide it, in which case that check is skipped.
        /// </summary>
        public static IntegrityResult Verify(byte[] bytes, string expectedSha256Hex, long? expectedByteSize)
        {
            if (bytes == null || bytes.Length == 0)
            {
                return IntegrityResult.Failure(null, 0, "Downloaded content is empty.");
            }

            var actualSha256 = ComputeSha256Hex(bytes);
            var actualByteSize = (long)bytes.Length;

            if (expectedByteSize.HasValue && expectedByteSize.Value > 0 && expectedByteSize.Value != actualByteSize)
            {
                return IntegrityResult.Failure(
                    actualSha256,
                    actualByteSize,
                    $"Byte size mismatch: expected {expectedByteSize.Value}, got {actualByteSize}.");
            }

            if (!string.IsNullOrWhiteSpace(expectedSha256Hex))
            {
                var expected = expectedSha256Hex.Trim();
                if (!IsValidSha256Hex(expected))
                {
                    return IntegrityResult.Failure(
                        actualSha256,
                        actualByteSize,
                        "Invalid manifest hash format: expected 64 lowercase or uppercase hex characters.");
                }

                if (!string.Equals(expected, actualSha256, StringComparison.OrdinalIgnoreCase))
                {
                    return IntegrityResult.Failure(
                        actualSha256,
                        actualByteSize,
                        $"SHA256 mismatch: expected {expected}, got {actualSha256}.");
                }
            }

            return IntegrityResult.Success(actualSha256, actualByteSize);
        }

        public static bool IsValidSha256Hex(string value)
        {
            if (string.IsNullOrWhiteSpace(value) || value.Length != 64)
            {
                return false;
            }

            for (var i = 0; i < value.Length; i++)
            {
                var c = value[i];
                var isHex = (c >= '0' && c <= '9') ||
                            (c >= 'a' && c <= 'f') ||
                            (c >= 'A' && c <= 'F');
                if (!isHex)
                {
                    return false;
                }
            }

            return true;
        }
    }
}
