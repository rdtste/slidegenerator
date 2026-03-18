import { Injectable, Logger } from '@nestjs/common';

@Injectable()
export class PreviewService {
  private readonly logger = new Logger(PreviewService.name);

  async renderHtml(markdown: string, themeCss?: string): Promise<string> {
    // Dynamic import because @marp-team/marp-core is ESM
    const { Marp } = await (Function('return import("@marp-team/marp-core")')() as Promise<typeof import('@marp-team/marp-core')>);

    const marp = new Marp({ html: true });
    const { html, css } = marp.render(markdown);

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
    body { margin: 0; background: #1a1d27; display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 16px; }
    svg[data-marpit-svg] { width: 100%; height: auto; box-shadow: 0 4px 24px rgba(0,0,0,0.5); border-radius: 4px; transition: outline 0.2s; }
    svg[data-marpit-svg].active-slide { outline: 3px solid #3b82f6; outline-offset: 2px; }
  </style>
</head>
<body>
${html}
<script>
  window.addEventListener('message', function(e) {
    if (e.data && typeof e.data.slideIndex === 'number') {
      var slides = document.querySelectorAll('svg[data-marpit-svg]');
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
}
