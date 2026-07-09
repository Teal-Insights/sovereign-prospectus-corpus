import { Marked } from 'marked';
const md = new Marked({
  gfm: true,
  renderer: {
    html: () => 'STRIPPED',
  }
});
console.log(md.parse('| a | b |\n| --- | --- |\n| <img src=x onerror=alert(1)> | 1 |'));
