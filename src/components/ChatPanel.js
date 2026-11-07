"use client";

import { useState } from "react";
import { askQuestion } from "../lib/api";

function getRuleUrl(id, clauses) {
  const rule = id.match(/^V(\d{3})(?:\.\d+)*$/i);
  if (!rule) return null;

  const clause = clauses.find((item) => item.id.toUpperCase() === id.toUpperCase());
  const chapterUrl =
    clause?.source_url || `https://www.access-board.gov/pvag/ch-v${rule[1][0]}/`;
  const url = new URL(chapterUrl);
  url.hash = `v${rule[1].toLowerCase()}`;
  return url.href;
}

function formatReferences(text, keyPrefix, clauses) {
  return text.split(/(V\d{3}(?:\.\d+)*)/gi).map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    const href = getRuleUrl(part, clauses);
    return href ? (
      <a key={key} href={href} target="_blank" rel="noreferrer">
        {part}
      </a>
    ) : (
      part
    );
  });
}

function formatInline(text, keyPrefix, clauses) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={key}>
          {formatReferences(part.slice(2, -2), key, clauses)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={key}>{formatReferences(part.slice(1, -1), key, clauses)}</em>;
    }
    return formatReferences(part, key, clauses);
  });
}

function FormattedAnswer({ text, clauses }) {
  const blocks = [];
  let paragraph = [];
  let list = [];
  let listType = null;

  function flushParagraph() {
    if (paragraph.length) {
      blocks.push(
        <p key={`paragraph-${blocks.length}`}>
          {formatInline(paragraph.join(" "), `paragraph-${blocks.length}`, clauses)}
        </p>,
      );
      paragraph = [];
    }
  }

  function flushList() {
    if (list.length) {
      const List = listType === "ordered" ? "ol" : "ul";
      blocks.push(
        <List key={`list-${blocks.length}`}>
          {list.map((item, index) => (
            <li key={index}>
              {formatInline(item, `list-${blocks.length}-${index}`, clauses)}
            </li>
          ))}
        </List>,
      );
      list = [];
      listType = null;
    }
  }

  text.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    const unorderedItem = line.match(/^[-*]\s+(.+)$/);
    const orderedItem = line.match(/^\d+[.)]\s+(.+)$/);

    if (!line) {
      flushParagraph();
      flushList();
    } else if (heading) {
      flushParagraph();
      flushList();
      blocks.push(
        <h3 key={`heading-${blocks.length}`}>
          {formatInline(heading[1], `heading-${blocks.length}`, clauses)}
        </h3>,
      );
    } else if (unorderedItem || orderedItem) {
      flushParagraph();
      const nextListType = orderedItem ? "ordered" : "unordered";
      if (listType && listType !== nextListType) flushList();
      listType = nextListType;
      list.push((unorderedItem || orderedItem)[1]);
    } else {
      flushList();
      paragraph.push(line);
    }
  });

  flushParagraph();
  flushList();

  return <div className="chat-answer-content">{blocks}</div>;
}

export default function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event) {
    event.preventDefault();
    const submittedQuestion = question.trim();
    if (!submittedQuestion || pending) return;

    setPending(true);
    setError("");
    try {
      const response = await askQuestion(submittedQuestion);
      setMessages((current) => [...current, { question: submittedQuestion, response }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The question could not be answered.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card chat-panel" aria-labelledby="chat-heading">
      <h2 id="chat-heading">Ask about compliance rules</h2>
      <p className="hint">Ask a question about the vessel rules and get an answer with source clauses.</p>

      {messages.length > 0 && (
        <div className="chat-messages" aria-live="polite" aria-busy={pending}>
          {messages.map(({ question: asked, response }, index) => (
            <article className="chat-exchange" key={index}>
              <p className="chat-question">{asked}</p>
              <div className="chat-answer">
                <FormattedAnswer text={response.answer} clauses={response.clauses} />
                {response.relevant && response.clauses.length > 0 && (
                  <div className="chat-sources">
                    <strong>Sources</strong>
                    <ul>
                      {response.clauses.map((clause) => (
                        <li key={clause.id}>
                          <a href={clause.source_url} target="_blank" rel="noreferrer">
                            {clause.title}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </article>
          ))}
          {pending && <p className="hint" role="status">Thinking...</p>}
        </div>
      )}

      <form className="chat-form" onSubmit={onSubmit}>
        <label htmlFor="chat-question">Your question</label>
        <textarea
          id="chat-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={2000}
          placeholder="For example: What are the requirements for escape routes?"
          required
        />
        <div className="chat-form-footer">
          <span className="hint">Up to 2,000 characters</span>
          <button type="submit" className="primary" disabled={pending || !question.trim()}>
            {pending ? "Sending..." : "Ask"}
          </button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </form>
    </section>
  );
}
