"use client";

import { useState } from "react";

export default function ShipcheckReview({ data, onSubmit, disabled }) {
  const [decisions, setDecisions] = useState(
    () => data.claims.map(({ index }) => ({ index, decision: "accept" })),
  );
  const [acknowledge, setAcknowledge] = useState(false);
  const decisionFor = (index) => decisions.find((item) => item.index === index)?.decision;
  const updateDecision = (index, decision) => {
    setDecisions((current) =>
      current.map((item) => (item.index === index ? { ...item, decision } : item)),
    );
  };
  const acceptAll = () => {
    setDecisions((current) =>
      current.map((item) => ({ ...item, decision: "accept" })),
    );
  };
  const unresolved = decisions.filter((item) => !item.decision).length;
  const blocked = unresolved > 0 || (data.invalid_sections.length > 0 && !acknowledge);

  return (
    <section className="card claim-review" aria-labelledby="review-heading">
      <h2 id="review-heading">Review extracted requirements</h2>
      <p className="hint">
        Confirm which extracted requirements should be included in the rule check. Reject claims that are inaccurate or irrelevant.
      </p>
      <div className="review-toolbar">
        <button
          type="button"
          className="secondary"
          onClick={acceptAll}
          disabled={disabled}
        >
          Accept all claims
        </button>
        <span className="hint">{decisions.filter((item) => item.decision === "accept").length} of {decisions.length} included</span>
      </div>
      {data.claims.length === 0 && <p className="review-empty">No claims were extracted.</p>}
      <ol className="claim-list">
        {data.claims.map(({ index, claim }) => (
          <li className="claim-card" key={index}>
            <div className="finding-title-row">
              <strong>{claim.subject}</strong>
              <span className="hint">Section {claim.section_id}</span>
            </div>
            <p>{claim.quote}</p>
            <div className="review-actions">
              <button
                type="button"
                className={decisionFor(index) === "accept" ? "decision selected" : "decision"}
                onClick={() => updateDecision(index, "accept")}
                disabled={disabled}
              >
                Include
              </button>
              <button
                type="button"
                className={decisionFor(index) === "reject" ? "decision selected reject" : "decision"}
                onClick={() => updateDecision(index, "reject")}
                disabled={disabled}
              >
                Exclude
              </button>
            </div>
          </li>
        ))}
      </ol>
      {data.invalid_sections.length > 0 && (
        <label className="acknowledgement">
          <input
            type="checkbox"
            checked={acknowledge}
            onChange={(event) => setAcknowledge(event.target.checked)}
            disabled={disabled}
          />
          Continue despite {data.invalid_sections.length} section(s) that could not be extracted.
        </label>
      )}
      <button
        type="button"
        className="primary"
        disabled={disabled || blocked}
        onClick={() => onSubmit(decisions, acknowledge)}
      >
        Accept all and run checks
      </button>
      {unresolved > 0 && <p className="hint">Resolve {unresolved} remaining claim decision(s).</p>}
    </section>
  );
}
