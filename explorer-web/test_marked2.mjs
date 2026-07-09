import { Marked } from 'marked';
const md = new Marked({
  renderer: {
    html: () => 'RENDERER_HTML',
  }
});
console.log(md.parse('<a/href="javascript:alert(1)">click</a>'));
console.log(md.parse('<svg/onload=alert(1)>'));
