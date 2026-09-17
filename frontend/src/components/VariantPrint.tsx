import { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
// KaTeX din bundle (servit din 'self') — permis de CSP, spre deosebire de CDN.
import 'katex/dist/katex.min.css';
// @ts-expect-error - contrib/auto-render nu are tipuri publicate
import renderMathInElement from 'katex/contrib/auto-render';
import { getVariantDocument } from '../api';

/* Pagina de print pentru variante (subiect / rezolvare / barem).
   Refolosește layout-ul HTML generat de backend, dar randează formulele cu
   KaTeX din bundle-ul aplicației (nu de pe CDN, care e blocat de CSP).
   Utilizatorul apasă „Descarcă PDF" → printul nativ → „Salvează ca PDF". */

const MODE_ENDPOINT = {
  exam: 'preview-exam',
  solutions: 'preview-solutions',
  barem: 'preview-barem',
} as const;

type Mode = keyof typeof MODE_ENDPOINT;

export default function VariantPrint() {
  const { variantId } = useParams<{ variantId: string }>();
  const [params] = useSearchParams();
  const rawMode = params.get('mode') as Mode | null;
  const mode: Mode = rawMode && rawMode in MODE_ENDPOINT ? rawMode : 'exam';

  const [styleCss, setStyleCss] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!variantId) return;
    setLoading(true);
    getVariantDocument(variantId, MODE_ENDPOINT[mode])
      .then(async (res) => {
        const text = await (res.data as Blob).text();
        const doc = new DOMParser().parseFromString(text, 'text/html');
        const css = Array.from(doc.querySelectorAll('style')).map((s) => s.innerHTML).join('\n');
        const printable = doc.getElementById('printable') || doc.body;
        setStyleCss(css);
        setContent(printable.innerHTML);
      })
      .catch(() => setError('Nu am putut genera documentul. Verifică abonamentul sau reîncearcă.'))
      .finally(() => setLoading(false));
  }, [variantId, mode]);

  useEffect(() => {
    if (!content || !ref.current) return;
    try {
      renderMathInElement(ref.current, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
        ],
        throwOnError: false,
      });
    } catch {
      /* dacă o formulă e malformată, o lăsăm ca atare */
    }
  }, [content]);

  const title = mode === 'solutions' ? 'Rezolvare' : mode === 'barem' ? 'Barem' : 'Subiect';

  return (
    <div className="vp-root">
      {/* Stilurile de layout venite din documentul generat de backend */}
      <style>{styleCss}</style>
      <style>{`
        .vp-bar {
          position: sticky; top: 0; z-index: 10;
          display: flex; align-items: center; gap: 12px;
          background: #0f172a; color: #fff; padding: 10px 16px;
        }
        .vp-hint { margin-right: auto; opacity: 0.85; font-size: 0.85rem; }
        .vp-print-btn {
          background: #2563eb; color: #fff; border: none; border-radius: 8px;
          padding: 8px 16px; font: inherit; font-weight: 700; cursor: pointer;
        }
        .vp-print-btn:hover { background: #1d4ed8; }
        .vp-doc { max-width: 820px; margin: 0 auto; padding: 20px 16px 60px; }
        .vp-state { padding: 40px 16px; text-align: center; color: #475569; }
        @media print {
          .vp-bar { display: none !important; }
          .vp-doc { max-width: 100%; margin: 0; padding: 0; }
        }
      `}</style>

      {!loading && !error && (
        <div className="vp-bar">
          <span className="vp-hint">{title} pregătit — apasă „Descarcă PDF" și alege „Salvează ca PDF".</span>
          <button className="vp-print-btn" type="button" onClick={() => window.print()}>⬇️ Descarcă PDF</button>
        </div>
      )}

      {loading && <div className="vp-state">Se generează documentul…</div>}
      {error && <div className="vp-state">{error}</div>}
      {!loading && !error && (
        <div className="vp-doc content" ref={ref} dangerouslySetInnerHTML={{ __html: content }} />
      )}
    </div>
  );
}
