"use client";

function claimDescription(claim) {
  const value = [claim.value, claim.unit].filter(Boolean).join(" ");
  return [claim.quantity, value].filter(Boolean).join(": ");
}

export default function ShipcheckReview({
  review,
  onDecision,
  acknowledgeIncomplete,
  onAcknowledgeIncomplete,
  onSubmit,
  submitting,
  retrying,
}) {
  const claims = review.claims ?? [];
  const allReviewed = claims.every((item) => item.decision === "accept" || item.decision === "reject");
  const hasInvalidSections = (review.invalid_sections ?? []).length > 0;
  const canSubmit = allReviewed && (!hasInvalidSections || acknowledgeIncomplete) && !submitting;

  return (
    <section className="card claim-review" aria-labelledby="claim-review-heading">
      <h2 id="claim-review-heading">Review extracted claims</h2>
      <p className="hint">
        Check each extracted value against the specification before continuing. Only claims you accept
        will be checked against the rules.
      </p>

      {claims.length === 0 ? (
        <p className="empty review-empty">No checkable claims were extracted. Continue to generate the report.</p>
      ) : (
        <ol className="claim-list">
          {claims.map(({ index, claim, decision }) => (
            <li className="claim-card" key={index}>
              <div className="claim-card-heading">
                <strong>{claim.subject || "Extracted claim"}</strong>
                <span>{claimDescription(claim) || "Value not specified"}</span>
                {claim.section_id && <span className="hint">Section {claim.section_id}</span>}
              </div>
              {claim.quote && <blockquote>{claim.quote}</blockquote>}
              <div className="claim-decisions" aria-label={`Review claim ${index + 1}`}>
                <button
                  type="button"
                  className={decision === "accept" ? "selected accept" : ""}
                  aria-pressed={decision === "accept"}
                  onClick={() => onDecision(index, "accept")}
                >
                  Accept
                </button>
                <button
                  type="button"
                  className={decision === "reject" ? "selected reject" : ""}
                  aria-pressed={decision === "reject"}
                  onClick={() => onDecision(index, "reject")}
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}

      {hasInvalidSections && (
        <div className="incomplete-extraction">
          <strong>Some sections could not be processed</strong>
          <ul>
            {review.invalid_sections.map((section) => (
              <li key={section.section_id}>
                Section {section.section_id}: {section.reason}
              </li>
            ))}
          </ul>
          <label>
            <input
              type="checkbox"
              checked={acknowledgeIncomplete}
              onChange={(event) => onAcknowledgeIncomplete(event.target.checked)}
            />
            I understand the report may be incomplete and want to continue.
          </label>
        </div>
      )}

      <button type="button" className="primary" disabled={!canSubmit} onClick={onSubmit}>
        {submitting ? "Checking specification..." : retrying ? "Retry check" : "Run checks"}
      </button>
      {!allReviewed && <p className="hint" role="status">Accept or reject every claim to continue.</p>}
    </section>
  );
}
