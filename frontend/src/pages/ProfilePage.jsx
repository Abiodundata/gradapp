import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Alert, Field, Loading, PageHeader } from "../components/ui";
import { Icon } from "../icons";

export const EMPTY_PROFILE = {
  intended_degree_level: "",
  previous_degree: "",
  previous_field_of_study: "",
  gpa: "",
  academic_interests: "",
  research_interests: "",
  career_goals: "",
  preferred_programs: "",
  preferred_locations: "",
  tuition_budget: "",
  funding_requirement: "preferred",
};

const EDITABLE = Object.keys(EMPTY_PROFILE);

/** Create Academic Profile use case. */
export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [message, setMessage] = useState({ text: "", tone: "success" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api("/auth/profile/")
      .then((data) => setProfile({ ...EMPTY_PROFILE, ...Object.fromEntries(EDITABLE.map((key) => [key, data[key] ?? ""])) }))
      .catch((err) => { setProfile(EMPTY_PROFILE); setMessage({ text: err.message, tone: "error" }); });
  }, []);

  const update = (event) => setProfile({ ...profile, [event.target.name]: event.target.value });

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setMessage({ text: "", tone: "success" });
    const payload = {
      ...profile,
      gpa: profile.gpa === "" ? null : profile.gpa,
      tuition_budget: profile.tuition_budget === "" ? null : profile.tuition_budget,
    };
    try {
      const data = await api("/auth/profile/", { method: "PATCH", body: payload });
      setProfile({ ...EMPTY_PROFILE, ...Object.fromEntries(EDITABLE.map((key) => [key, data[key] ?? ""])) });
      setMessage({ text: "Profile saved. Your recommendations are updated.", tone: "success" });
    } catch (err) {
      setMessage({ text: err.message, tone: "error" });
    } finally {
      setSaving(false);
    }
  }

  if (!profile) return <div className="page"><Loading label="Loading profile…" /></div>;

  return (
    <div className="page narrow">
      <PageHeader eyebrow="Academic profile" title="Your student profile">
        GradApp uses this to recommend programs and match you with potential advisors. Update it anytime.
      </PageHeader>
      <form className="panel form-grid" onSubmit={save}>
        <h3 className="full">Degree and background</h3>
        <Field label="Intended degree">
          <select name="intended_degree_level" value={profile.intended_degree_level} onChange={update}>
            <option value="">Not decided</option>
            <option value="masters">Master’s</option>
            <option value="doctoral">Doctoral</option>
            <option value="other">Other graduate degree</option>
          </select>
        </Field>
        <Field label="GPA (4.0 scale)">
          <input type="number" min="0" max="4" step="0.01" name="gpa" value={profile.gpa} onChange={update} />
        </Field>
        <Field label="Previous degree"><input name="previous_degree" value={profile.previous_degree} onChange={update} placeholder="B.S. Computer Science" /></Field>
        <Field label="Previous field of study"><input name="previous_field_of_study" value={profile.previous_field_of_study} onChange={update} placeholder="Computer Science" /></Field>

        <h3 className="full">Interests and goals</h3>
        <Field label="Academic interests" full hint="Separate topics with commas.">
          <textarea name="academic_interests" value={profile.academic_interests} onChange={update} placeholder="Artificial intelligence, data science, software engineering" />
        </Field>
        <Field label="Research interests" full hint="Used to match you with faculty, e.g. “computer vision, robotics”.">
          <textarea name="research_interests" value={profile.research_interests} onChange={update} placeholder="Computer vision, reinforcement learning" />
        </Field>
        <Field label="Career goals" full>
          <textarea name="career_goals" value={profile.career_goals} onChange={update} placeholder="Research scientist, industry ML engineer…" />
        </Field>
        <Field label="Preferred programs" full hint="Program names or fields you are considering.">
          <input name="preferred_programs" value={profile.preferred_programs} onChange={update} placeholder="Computer Science, Data Science" />
        </Field>

        <h3 className="full">Location and cost</h3>
        <Field label="Preferred locations" hint="Cities, states or countries, separated by commas.">
          <input name="preferred_locations" value={profile.preferred_locations} onChange={update} placeholder="Texas, California, Canada" />
        </Field>
        <Field label="Annual tuition budget (USD)">
          <input type="number" min="0" step="1000" name="tuition_budget" value={profile.tuition_budget} onChange={update} />
        </Field>
        <Field label="Funding" full>
          <select name="funding_requirement" value={profile.funding_requirement} onChange={update}>
            <option value="required">I need funding to attend</option>
            <option value="preferred">Funding preferred</option>
            <option value="not_required">Funding not required</option>
          </select>
        </Field>

        <div className="form-actions full">
          <Alert tone={message.tone}>{message.text}</Alert>
          <Link className="secondary" to="/recommendations"><Icon name="sparkle" size={17} />See recommendations</Link>
          <button className="primary" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
        </div>
      </form>
    </div>
  );
}
