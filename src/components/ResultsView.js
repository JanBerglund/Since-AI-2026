"use client";

import Image from "next/image";

const verdictLabels = {
  fine: "Fine",
  not_fine: "Not fine",
  unknown: "Cannot determine",
};

export default function ResultsView({ result }) {
  const { summary, findings = [], images = [] } = result;

  return (
    <section className="card results" aria-labelledby="results-heading">
      <h2 id="results-heading">3. Result</h2>
      <p className="summary">
        {summary.checked} checked:
        <span className="badge fine">{summary.fine} fine</span>
        <span className="badge not-fine">{summary.not_fine} not fine</span>
        <span className="badge unknown">{summary.unknown} cannot determine</span>
      </p>

      {images.length > 0 && (
        <div className="result-images">
          {images.map((image) => (
            <figure className="result-image" key={image.page}>
              <Image
                src={image.url}
                alt={`Compliance check results for page ${image.page}`}
                width={1200}
                height={850}
                unoptimized
              />
              <figcaption>Marked drawing — page {image.page}</figcaption>
            </figure>
          ))}
        </div>
      )}

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
                <td>{finding.clause || finding.rule}</td>
                <td>{finding.page}</td>
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
