"use client";

import Image from "next/image";

const verdictLabels = {
  pass: "Pass",
  fail: "Fail",
  unknown: "Unknown",
};

function PageLink({ page, pagesByNumber }) {
  const documentPage = pagesByNumber.get(page);
  if (!documentPage) return <span>Page {page}</span>;
  return (
    <a href={documentPage.image} target="_blank" rel="noreferrer">
      View page {page}
    </a>
  );
}

export default function ResultsView({ result }) {
  const findings = result.findings ?? [];
  const pages = result.pages ?? [];
  const pagesByNumber = new Map(pages.map((page) => [page.n, page]));
  const counts = findings.reduce(
    (total, finding) => {
      total[finding.verdict] = (total[finding.verdict] ?? 0) + 1;
      return total;
    },
    { pass: 0, fail: 0, unknown: 0 },
  );

  return (
    <section className="card results" aria-labelledby="results-heading">
      <div className="results-heading">
        <div>
          <h2 id="results-heading">Specification check results</h2>
          <p className="hint">{findings.length} findings across {pages.length} document pages</p>
        </div>
        {result.pdf && (
          <a className="results-pdf-link" href={result.pdf} target="_blank" rel="noreferrer">
            Open uploaded PDF
          </a>
        )}
      </div>

      <p className="summary">
        <span className="badge pass">{counts.pass} pass</span>
        <span className="badge fail">{counts.fail} fail</span>
        <span className="badge unknown">{counts.unknown} unknown</span>
      </p>

      {findings.length === 0 ? (
        <p className="empty">No findings were produced from the accepted claims.</p>
      ) : (
        <ol className="finding-list">
          {findings.map((finding) => (
            <li className="finding-card" key={finding.id}>
              <div className="finding-title-row">
                <h3>{finding.title}</h3>
                <span className={`badge ${finding.verdict}`}>
                  {verdictLabels[finding.verdict] ?? finding.verdict}
                </span>
              </div>
              <p>{finding.reason}</p>
              <p className="finding-meta">
                {finding.kind === "consistency" ? "Specification consistency" : "Rule comparison"}
                {finding.scope && finding.scope !== "not_applicable" && ` · Scope: ${finding.scope.replaceAll("_", " ")}`}
                {finding.hypothetical && finding.hypothetical !== "not_applicable" &&
                  ` · PVAG comparison: ${finding.hypothetical}`}
              </p>

              {finding.clause && (
                <blockquote className="rule-quote">
                  <a href={finding.clause.url} target="_blank" rel="noreferrer">
                    {finding.clause.id}
                  </a>
                  {finding.clause.quote && <span>{finding.clause.quote}</span>}
                </blockquote>
              )}

              {finding.spec_refs?.length > 0 && (
                <div className="spec-references">
                  <strong>Specification evidence</strong>
                  <ul>
                    {finding.spec_refs.map((reference, index) => (
                      <li key={`${reference.section}-${reference.page}-${index}`}>
                        <span>Section {reference.section}: “{reference.quote}”</span>
                        {" "}
                        <PageLink page={reference.page} pagesByNumber={pagesByNumber} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {pages.length > 0 && (
        <details className="report-pages">
          <summary>Rendered document pages ({pages.length})</summary>
          <div className="report-page-grid">
            {pages.map((page) => (
              <a href={page.image} target="_blank" rel="noreferrer" key={page.n}>
                <Image
                  src={page.image}
                  alt={`Document page ${page.n}`}
                  width={page.w}
                  height={page.h}
                  unoptimized
                />
                <span>Page {page.n}</span>
              </a>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
