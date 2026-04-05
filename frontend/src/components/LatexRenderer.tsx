import { useEffect, useRef, useState } from 'react';
import 'katex/dist/katex.min.css';
import { BlockMath, InlineMath } from 'react-katex';

interface Props {
  text: string;
  className?: string;
}

function LatexContent({ text, className }: Props) {
  if (!text) return null;

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

export default function LatexRenderer({ text, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref}>
      {visible ? <LatexContent text={text} className={className} /> : <span style={{ minHeight: '1.5em', display: 'block' }} />}
    </div>
  );
}
