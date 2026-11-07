"use client";

const verdictLabels = {
  fine: "Fine",
  not_fine: "Not fine",
  unknown: "Cannot determine",
  not_applicable: "Does not apply",
};

export default function ResultsView({ result }) {
  const { summary, findings = [] } = result;

  return (
    <section className="card results" aria-labelledby="results-heading">
      <h2 id="results-heading">Review findings</h2>
      <p className="summary">
        {summary.checked} checked:
        <span className="badge fine">{summary.fine} fine</span>
        <span className="badge not-fine">{summary.not_fine} not fine</span>
        <span className="badge unknown">{summary.unknown} cannot determine</span>
        <span className="badge not-applicable">{summary.not_applicable ?? 0} does not apply</span>
      </p>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Result</th>
              <th scope="col">Item</th>
              <th scope="col">Why</th>
              <th scope="col">Rule</th>
              <th scope="col">Page</th>
              <th scope="col">Source</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding) => (
              <tr key={finding.number}>
                <td>{finding.number}</td>
                <td>
                  <span className={`badge ${finding.verdict.replace("_", "-")}`}>
                    {verdictLabels[finding.verdict] ?? finding.verdict}
                  </span>
                </td>
                <td>{finding.item}</td>
                <td>{finding.label}</td>
                <td>
                  {finding.clause || finding.rule}
                  {finding.verified === false && (
                    <small className="rule-unverified">Rule not yet verified</small>
                  )}
                </td>
                <td>{finding.page ?? "Unknown"}</td>
                <td>{finding.source}</td>
              </tr>
            ))}
            {findings.length === 0 && (
              <tr>
                <td colSpan="7" className="empty">
                  No findings were returned for these pages.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
