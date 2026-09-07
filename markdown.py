import re

def clean_markdown(md_text):
    md_text = md_text.replace("\\n", "\n")

    # Remove horizontal rules
    md_text = re.sub(r'\n?-{3,}\n?', '\n', md_text)

    # Fix titles
    def replace_title(match):
        title = match.group(1)
        return f"\n\n{title}\n" + "-" * len(title)

    md_text = re.sub(r'###\s*\*\*(.*?)\*\*', replace_title, md_text)

    # Remove bold markers
    md_text = md_text.replace('**', '')

    # Replace only bullet-list hyphens at start of line
    md_text = re.sub(r'(?m)^\s*-\s+', '• ', md_text)

    return md_text.strip()


with open("input.txt", "r", encoding="utf-8") as f:
    md = f.read()

clean_text = clean_markdown(md)

with open("output.txt", "w", encoding="utf-8") as f:
    f.write(clean_text)

print("✅ Fichier output.txt généré avec succès !")