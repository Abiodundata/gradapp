import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ProfilePage from "../pages/ProfilePage";

const PROFILE = {
  id: 1, user: { id: 1 }, intended_degree_level: "masters", previous_degree: "", previous_field_of_study: "",
  gpa: null, academic_interests: "", research_interests: "", career_goals: "", preferred_programs: "",
  preferred_locations: "", tuition_budget: null, funding_requirement: "preferred",
};

describe("ProfilePage", () => {
  it("sends a valid funding_requirement choice and nulls for empty numbers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => PROFILE })
      .mockImplementationOnce(async (_url, options) => ({ ok: true, status: 200, json: async () => ({ ...PROFILE, ...JSON.parse(options.body) }) }));

    render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ProfilePage /></MemoryRouter>);
    const funding = await screen.findByLabelText("Funding");
    await userEvent.selectOptions(funding, "required");
    await userEvent.type(screen.getByLabelText(/Research interests/), "computer vision");
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const body = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(body.funding_requirement).toBe("required");
    expect(body.research_interests).toBe("computer vision");
    expect(body.gpa).toBeNull();
    expect(body.tuition_budget).toBeNull();
    expect(body).not.toHaveProperty("user");
    expect(await screen.findByText(/Profile saved/)).toBeInTheDocument();
  });
});
