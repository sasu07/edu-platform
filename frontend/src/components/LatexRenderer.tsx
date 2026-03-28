import 'katex/dist/katex.min.css';
import { BlockMath, InlineMath } from 'react-katex';

interface Props {
  text: string;
  className?: string;
}

export default function LatexRenderer({ text, className }: Props) {
  if (!text) return null;

  // Împarte textul în bucăți: $$...$$ (block), $...$ (inline), text simplu
  const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g);

  return (
    <span className={className} style={{ lineHeight: 1.8 }}>
      {parts.map((part, i) => {
        if (part.startsWith('$$') && part.endsWith('$$')) {
          const math = part.slice(2, -2).trim();
          return (
            <span key={i} style={{ display: 'block', margin: '8px 0' }}>
              <BlockMath math={math} errorColor="#dc2626" />
            </span>
          );
        }
        if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
          const math = part.slice(1, -1).trim();
          return <InlineMath key={i} math={math} errorColor="#dc2626" />;
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}
