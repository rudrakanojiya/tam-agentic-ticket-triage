"""Pure Markdown corpus loader; retrieval and chunking belong elsewhere."""
from dataclasses import dataclass
from pathlib import Path

KB_DIR = Path(__file__).resolve().parents[1] / 'knowledge-base'


@dataclass(frozen=True)
class KBArticle:
    article_id: str
    path: str
    title: str
    content: str


def load_kb_articles(directory: str | Path = KB_DIR) -> list[KBArticle]:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    articles = []
    for path in sorted(directory.rglob('*.md')):
        content = path.read_text(encoding='utf-8-sig')
        relative = path.relative_to(directory).as_posix()
        title = next((line[2:].strip() for line in content.splitlines()
                      if line.startswith('# ')), path.stem)
        articles.append(KBArticle(relative.removesuffix('.md'), relative, title, content))
    return articles
