"use client";

import Image from "next/image";
import { useState } from "react";

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
  const [activeTab, setActiveTab] = useState("results");
  const findings = result.findings ?? [];
  const pages = result.pages ?? [];
  const pagesByNumber = new Map(pages.map((page) => [page.n, page]));
  const ruleCounts = findings
    .filter((finding) => finding.kind === "pvag")
    .reduce(
      (total, finding) => {
        total[finding.verdict] = (total[finding.verdict] ?? 0) + 1;
        return total;
      },
      { pass: 0, fail: 0, unknown: 0 },
    );
  const details = result.ship_details ?? {};
  const selectedClaims = details.selected_claims ?? [];
  const consistencyCount = findings.filter((finding) => finding.kind === "consistency").length;
  const ruleComparisonCount = findings.filter((finding) => finding.kind === "pvag").length;
  const scopeResult = result.scope?.result ?? result.scope?.scope;
  const acceptedClaimCount = details.accepted_claims ?? selectedClaims.length;

  return (
    <section className="card results" aria-labelledby="results-heading">
      <div className="results-heading">
        <div>
          <h2 id="results-heading">Specification check</h2>
          <p className="hint">{findings.length} findings across {pages.length} document pages</p>
        </div>
      </div>

      <nav className="results-tabs" aria-label="Results sections">
        {[
          ["results", "Check results"],
          ["files", "PDF files"],
          ["stats", "Ship stats"],
        ].map(([id, label]) => (
          <button
            type="button"
            className={activeTab === id ? "results-tab active" : "results-tab"}
            aria-selected={activeTab === id}
            role="tab"
            key={id}
            onClick={() => setActiveTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === "results" && (
        <>
          <p className="summary">
            <span className="badge pass">{ruleCounts.pass} verified pass</span>
            <span className="badge fail">{ruleCounts.fail} verified fail</span>
            <span className="badge unknown">{ruleCounts.unknown} needs review</span>
          </p>
          <p className="finding-breakdown">
            {consistencyCount} specification conflict{consistencyCount === 1 ? "" : "s"} ·{" "}
            {ruleComparisonCount} rule comparison{ruleComparisonCount === 1 ? "" : "s"}
          </p>
          <p className="results-explanation">
            These totals cover generated findings, not every accepted requirement.
            An accepted requirement is not counted as a pass unless a PVAG rule was
            retrieved and the comparison was validated. Claims with missing,
            inconclusive, or irrelevant evidence are shown as needs review.
            {acceptedClaimCount > ruleComparisonCount &&
              ` ${acceptedClaimCount - ruleComparisonCount} accepted requirement(s) did not produce a rule comparison.`}
          </p>
          {scopeResult === "out_of_scope" && (
            <p className="results-explanation">
              PVAG is outside this vessel&apos;s calculated scope. The displayed
              rule comparisons are hypothetical and are not compliance results.
            </p>
          )}
          {findings.length === 0 ? (
            <p className="empty">No findings were produced from the selected claims.</p>
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
                      <a href={finding.clause.url} target="_blank" rel="noreferrer">{finding.clause.id}</a>
                      {finding.clause.quote && <span>{finding.clause.quote}</span>}
                    </blockquote>
                  )}
                  {finding.spec_refs?.length > 0 && (
                    <div className="spec-references">
                      <strong>Specification evidence</strong>
                      <ul>
                        {finding.spec_refs.map((reference, index) => (
                          <li key={`${reference.section}-${reference.page}-${index}`}>
                            <span>Section {reference.section}: “{reference.quote}”</span>{" "}
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
        </>
      )}

      {activeTab === "files" && (
        <div className="file-panel">
          <h3>Source PDF</h3>
          {result.pdf ? (
            <a className="results-pdf-link" href={result.pdf} target="_blank" rel="noreferrer">
              Open uploaded PDF
            </a>
          ) : <p className="empty">The uploaded PDF is not available.</p>}
          <h3>Rendered report pages</h3>
          {pages.length > 0 ? (
            <div className="report-page-grid">
              {pages.map((page) => (
                <a href={page.image} target="_blank" rel="noreferrer" key={page.n}>
                  <Image src={page.image} alt={`Document page ${page.n}`} width={page.w} height={page.h} unoptimized />
                  <span>Page {page.n}</span>
                </a>
              ))}
            </div>
          ) : <p className="empty">No rendered pages are available.</p>}
        </div>
      )}

      {activeTab === "stats" && (
        <div className="results-overview stats-panel">
          <div>
            <h3>Check summary</h3>
            <table className="details-table">
              <tbody>
                <tr><th scope="row">PDF pages</th><td>{details.pdf_pages || pages.length || "—"}</td></tr>
                <tr><th scope="row">Selected sections</th><td>{details.selected_sections || "—"}</td></tr>
                <tr><th scope="row">Accepted claims</th><td>{details.accepted_claims || "—"}</td></tr>
                <tr><th scope="row">Total findings</th><td>{findings.length}</td></tr>
                <tr><th scope="row">Specification conflicts</th><td>{consistencyCount}</td></tr>
                <tr><th scope="row">Rule comparisons</th><td>{ruleComparisonCount}</td></tr>
                <tr><th scope="row">Job ID</th><td className="monospace">{result.job_id || "—"}</td></tr>
              </tbody>
            </table>
          </div>
          <div>
            <h3>Verdict totals</h3>
            <p className="stat-number pass">{ruleCounts.pass}<span>Verified pass</span></p>
            <p className="stat-number fail">{ruleCounts.fail}<span>Verified fail</span></p>
            <p className="stat-number unknown">{ruleCounts.unknown}<span>Needs review</span></p>
          </div>
          <div className="selected-claims">
            <h3>Selected requirements</h3>
            {selectedClaims.length === 0 ? (
              <p className="empty">No requirements were included in the review.</p>
            ) : (
              <div className="claims-table-wrap">
                <table className="details-table claims-table">
                  <thead>
                    <tr>
                      <th scope="col">Requirement</th>
                      <th scope="col">Value</th>
                      <th scope="col">Section</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedClaims.map((claim, index) => (
                      <tr key={`${claim.section}-${claim.quantity}-${index}`}>
                        <td>
                          <strong>{claim.subject}</strong>
                          <span className="claim-quantity">{claim.quantity}</span>
                        </td>
                        <td>{claim.value} {claim.unit}</td>
                        <td>{claim.section}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
