import { Injectable, Logger } from '@nestjs/common';

@Injectable()
export class PreviewService {
  private readonly logger = new Logger(PreviewService.name);

  async renderHtml(
    markdown: string,
    themeCss?: string,
    slideWidthCm?: number,
    slideHeightCm?: number,
  ): Promise<string> {
    // Dynamic import because @marp-team/marp-core is ESM
    const { Marp } = await (Function('return import("@marp-team/marp-core")')() as Promise<typeof import('@marp-team/marp-core')>);

    const marp = new Marp({ html: true });

    // Replace ![desc](placeholder) with inline SVG data URIs
    let processedMarkdown = this.replacePlaceholderImages(markdown);
    if (slideWidthCm && slideHeightCm) {
      const widthPx = Math.round(slideWidthCm / 2.54 * 96);
      const heightPx = Math.round(slideHeightCm / 2.54 * 96);
      const sizeDirective = `---\nmarp: true\nsize: ${widthPx}px ${heightPx}px\n---\n`;
      // Replace existing frontmatter or prepend
      if (processedMarkdown.startsWith('---')) {
        processedMarkdown = processedMarkdown.replace(
          /^---[\s\S]*?---/,
          `---\nmarp: true\nsize: ${widthPx}px ${heightPx}px\n---`,
        );
      } else {
        processedMarkdown = sizeDirective + processedMarkdown;
      }
    }

    const { html, css } = marp.render(processedMarkdown);

    const templateStyle = themeCss
      ? `<style>/* Template Theme Override */\n${themeCss}</style>`
      : '';

    this.logger.log('Rendered Marp preview HTML');

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>${css}</style>
  ${templateStyle}
  <style>
    html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #1a1d27; }
    body { display: flex; align-items: center; justify-content: center; }
    /* Single slide: fill viewport. Multiple slides: scroll vertically. */
    body.multi { flex-direction: column; align-items: center; gap: 16px; padding: 16px; overflow-y: auto; height: auto; }
    svg[data-marpit-svg] { max-width: 100%; max-height: 100%; box-shadow: 0 4px 24px rgba(0,0,0,0.5); border-radius: 4px; }
    body.multi svg[data-marpit-svg] { max-height: none; width: 100%; height: auto; }
    svg[data-marpit-svg].active-slide { outline: 3px solid #3b82f6; outline-offset: 2px; }
  </style>
</head>
<body>
${html}
<script>
  var slides = document.querySelectorAll('svg[data-marpit-svg]');
  if (slides.length > 1) document.body.classList.add('multi');
  window.addEventListener('message', function(e) {
    if (e.data && typeof e.data.slideIndex === 'number') {
      slides.forEach(function(s) { s.classList.remove('active-slide'); });
      var target = slides[e.data.slideIndex];
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.add('active-slide');
      }
    }
  });
</script>
</body>
</html>`;
  }

  private replacePlaceholderImages(markdown: string): string {
    return markdown.replace(
      /!\[([^\]]*)\]\(placeholder\)/g,
      (_match, alt: string) => {
        const escaped = alt
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">`
          + `<rect width="800" height="450" rx="12" fill="#23272f"/>`
          + `<text x="400" y="200" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#9ca3af">🖼️ Bild-Platzhalter</text>`
          + `<text x="400" y="240" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#6b7280">${escaped}</text>`
          + `</svg>`;
        const dataUri = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
        return `![${alt}](${dataUri})`;
      },
    );
  }
}
