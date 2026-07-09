import { Marked } from 'marked';
const md = new Marked({
  renderer: {
    html: () => 'RENDERER_HTML',
  }
});
console.log(md.parse('block <div>\n</div>\n\ninline <span>test</span>'));
