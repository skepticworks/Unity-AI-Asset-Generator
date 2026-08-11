using System;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Importing
{
    /// <summary>
    /// Creates a material that references an imported texture.
    /// </summary>
    public sealed class MaterialFactory
    {
        static readonly string[] MainTextureProperties =
        {
            "_BaseMap",
            "_MainTex",
            "_BaseColorMap",
            "_BaseColorTexture"
        };

        public Material CreateMaterial(
            Texture2D texture,
            string destinationFolder,
            string desiredFileNameWithoutExtension,
            string shaderName)
        {
            if (texture == null)
            {
                throw new ArgumentNullException(nameof(texture));
            }

            if (string.IsNullOrWhiteSpace(shaderName))
            {
                throw new ArgumentException("Shader name is required.", nameof(shaderName));
            }

            var shader = Shader.Find(shaderName);
            if (shader == null)
            {
                throw new InvalidOperationException(
                    $"Shader '{shaderName}' was not found. Configure a shader available in this project " +
                    "(for example 'Universal Render Pipeline/Lit', 'Standard', or 'Unlit/Texture').");
            }

            var folder = AssetPathUtility.NormalizeAssetPath(destinationFolder);
            AssetPathUtility.EnsureAssetFolderExists(folder);
            var safeName = AssetPathUtility.SanitizeFileName(desiredFileNameWithoutExtension);
            var desiredPath = AssetPathUtility.CombineAssetPath(folder, safeName + ".mat");
            var uniquePath = AssetPathUtility.EnsureUniqueAssetPath(desiredPath);

            var material = new Material(shader)
            {
                name = PathWithoutExtension(uniquePath)
            };
            AssignMainTexture(material, texture);
            // For repeating textures, show UV tiling on the material by default (PS1-style surfaces).
            if (texture.wrapMode == TextureWrapMode.Repeat)
            {
                if (material.HasProperty("_BaseMap"))
                    material.SetTextureScale("_BaseMap", new Vector2(2f, 2f));
                else if (material.HasProperty("_MainTex"))
                    material.SetTextureScale("_MainTex", new Vector2(2f, 2f));
                else
                    material.mainTextureScale = new Vector2(2f, 2f);
            }

            AssetDatabase.CreateAsset(material, uniquePath);
            AssetDatabase.SaveAssets();
            EditorGUIUtility.PingObject(material);
            Selection.activeObject = material;
            return material;
        }

        static void AssignMainTexture(Material material, Texture2D texture)
        {
            foreach (var property in MainTextureProperties)
            {
                if (material.HasProperty(property))
                {
                    material.SetTexture(property, texture);
                    return;
                }
            }

            // Fallback: Unity's mainTexture helper when available.
            material.mainTexture = texture;
        }

        static string PathWithoutExtension(string assetPath)
        {
            var file = System.IO.Path.GetFileNameWithoutExtension(assetPath);
            return string.IsNullOrEmpty(file) ? "GeneratedMaterial" : file;
        }
    }
}
