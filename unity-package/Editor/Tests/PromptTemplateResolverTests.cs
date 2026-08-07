using NUnit.Framework;
using UnityAiAssets.Editor.Prompting;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class PromptTemplateResolverTests
    {
        [Test] public void ResolvesAndCleansEmptyModifiers()
        {
            var template = new PromptTemplate { Pattern = "{subject}, {style_modifiers}", Placeholders = { "subject", "style_modifiers" } };
            Assert.AreEqual("wall", PromptTemplateResolver.Resolve(template, "wall", new[] { "", " " }, "texture"));
        }
        [Test] public void RejectsUnknownPlaceholder()
        {
            var template = new PromptTemplate { Pattern = "{subject} {unsafe}", Placeholders = { "subject" } };
            Assert.Throws<System.FormatException>(() => PromptTemplateResolver.Resolve(template, "wall", null, "texture"));
        }
        [Test] public void RequiresSubject()
        {
            Assert.Throws<System.ArgumentException>(() => PromptTemplateResolver.Resolve(new PromptTemplate(), " ", null, "texture"));
        }
    }
}
