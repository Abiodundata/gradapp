import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Alert, Empty, Loading, PageHeader, ProgramCard } from "../components/ui";
import { Icon } from "../icons";

const COMPONENTS = [
  ["academic", "Academic fit", 35],
  ["location", "Location", 15],
  ["budget", "Budget", 15],
  ["funding", "Funding", 15],
  ["gpa", "GPA", 10],
  ["timing", "Timing", 10],
];

function ScoreBreakdown({ breakdown }) {
  return (
    <div className="breakdown" aria-label="Score breakdown">
      {COMPONENTS.map(([key, label, max]) => (
        <div key={key} className="breakdown-row">
          <span>{label}</span>
          <div className="bar" role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={breakdown[key]} aria-label={`${label} ${breakdown[key]} of ${max}`}>
            <div style={{ width: `${(100 * breakdown[key]) / max}%` }} />
          </div>
          <small>{breakdown[key]}/{max}</small>
        </div>
      ))}
    </div>
  );
}

function RecommendationDetails({ item }) {
  return (
    <div className="recommendation">
      <div className="score-ring" style={{ "--score": item.score }} aria-label={`Fit score ${item.score} out of 100`}>
        <strong>{item.score}</strong><small>fit</small>
      </div>
      <div className="recommendation-body">
        {item.reasons.length > 0 && (
          <ul className="reason-list good">
            {item.reasons.map((reason) => <li key={reason}><Icon name="check" size={15} />{reason}</li>)}
          </ul>
        )}
        {item.cautions.length > 0 && (
          <ul className="reason-list caution">
            {item.cautions.map((caution) => <li key={caution}><Icon name="alert" size={15} />{caution}</li>)}
          </ul>
        )}
        <details>
          <summary>How this score was calculated</summary>
          <ScoreBreakdown breakdown={item.breakdown} />
        </details>
      </div>
    </div>
  );
}

/** Get Personalized Recommendations use case. */
export default function RecommendationsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/ai/status/")
      .then((status) => api(`/recommendations/?limit=15${status.ai_enabled ? "&explain=true" : ""}`))
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Personalized recommendations"
        title="Programs that fit your profile"
        actions={<Link className="secondary" to="/profile"><Icon name="user" size={17} />Edit profile</Link>}
      >
        Ranked by how well each program matches your interests, location, budget, funding needs, GPA and timing.
        Scores describe fit, not your chances of admission.
      </PageHeader>
      <Alert>{error}</Alert>
      {!data && !error && <Loading label="Finding your best matches…" />}
      {data && !data.profile_complete && (
        <div className="callout">
          <Icon name="info" />
          <div>
            <strong>Complete your profile for better recommendations.</strong>
            <p>Add your interests, preferred locations, budget and GPA so GradApp can explain each match.</p>
          </div>
          <Link className="primary" to="/profile">Complete profile</Link>
        </div>
      )}
      {data?.summary && (
        <div className="callout ai">
          <Icon name="sparkle" />
          <div><strong>AI summary</strong><p>{data.summary}</p></div>
        </div>
      )}
      {data && data.results.length === 0 && (
        <Empty title="No matching programs yet">
          No programs match your intended degree level. Try changing it in your profile or browse all programs.
        </Empty>
      )}
      <div className="program-list">
        {data?.results.map((item) => (
          <ProgramCard key={item.program.id} program={item.program} extra={<RecommendationDetails item={item} />} />
        ))}
      </div>
    </div>
  );
}
