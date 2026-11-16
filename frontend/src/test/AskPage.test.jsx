import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import AskPage from "../pages/AskPage";

const ok = (body, status = 200) => ({ ok: true, status, json: async () => body });

const conversation = { id: 7, title: "UH computer science", updated_at: new Date().toISOString(), message_count: 2 };
const webReply = {
  conversation,
  saved: [],
  messages: [
    { id: 1, role: "user", content: "UH computer science", sources: [] },
    {
      id: 2, role: "assistant", ai_powered: true, web_searched: true,
      content: "UH offers an MS in Computer Science [W1].",
      sources: [
        { type: "web", ref: "W1", title: "MS in CS - UH", url: "https://www.uh.edu/cs/ms" },
        { type: "program", ref: "P20", id: 20, title: "Computer Science - University of Houston", saved: true, created: true },
      ],
    },
  ],
};

function renderAsk(path = "/ask") {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/ask" element={<AskPage />} />
        <Route path="/ask/:conversationId" element={<AskPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AskPage", () => {
  it("starts a saved conversation and shows web sources and saved records", async () => {
    const calls = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
      calls.push([url, options.method || "GET", options.body]);
      if (url.endsWith("/ai/status/")) return ok({ ai_enabled: true, web_search_enabled: true });
      if (url.includes("/conversations/?")) return ok({ results: [] });
      if (url.endsWith("/conversations/") && options.method === "POST") return ok({ id: 7 }, 201);
      if (url.endsWith("/conversations/7/messages/")) return ok(webReply, 201);
      if (url.endsWith("/conversations/7/")) return ok({ ...conversation, messages: webReply.messages });
      throw new Error(`unexpected ${url}`);
    });

    renderAsk();
    await userEvent.type(await screen.findByLabelText("Your question"), "UH computer science");
    await userEvent.click(screen.getByRole("button", { name: /^Send/ }));

    expect(await screen.findByText("Web search")).toBeInTheDocument();
    const ref = screen.getAllByText("W1")[0].closest("a");
    expect(ref).toHaveAttribute("href", "https://www.uh.edu/cs/ms");
    expect(screen.getByText(/Saved to GradApp for future searches \(1 new/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Computer Science - University of Houston" })).toHaveAttribute("href", "/programs/20");
    // The conversation appears in the sidebar so it can be continued later.
    expect(screen.getAllByText("UH computer science").length).toBeGreaterThan(0);

    const sent = calls.find(([url]) => url.endsWith("/conversations/7/messages/"));
    expect(JSON.parse(sent[2])).toMatchObject({ question: "UH computer science", search_web: false });
  });

  it("continues an existing conversation and can retry a question on the web", async () => {
    const recordsReply = [
      { id: 1, role: "user", content: "Data science programs?", sources: [] },
      { id: 2, role: "assistant", ai_powered: true, web_searched: false, content: "Try [P4].", sources: [{ type: "program", ref: "P4", id: 4, title: "Data Science" }] },
    ];
    let sentBody = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
      if (url.endsWith("/ai/status/")) return ok({ ai_enabled: true, web_search_enabled: true });
      if (url.includes("/conversations/?")) return ok({ results: [{ ...conversation, id: 3, title: "Data science programs?" }] });
      if (url.endsWith("/conversations/3/")) return ok({ id: 3, title: "Data science programs?", messages: recordsReply });
      if (url.endsWith("/conversations/3/messages/")) {
        sentBody = JSON.parse(options.body);
        return ok({ conversation: { ...conversation, id: 3 }, saved: [], messages: [
          { id: 3, role: "user", content: "Data science programs?", sources: [] },
          { id: 4, role: "assistant", ai_powered: true, web_searched: true, content: "From the web.", sources: [] },
        ] }, 201);
      }
      throw new Error(`unexpected ${url}`);
    });

    renderAsk("/ask/3");
    expect(await screen.findByRole("link", { name: "P4" })).toHaveAttribute("href", "/programs/4");
    await userEvent.click(screen.getByRole("button", { name: /Search the web/ }));
    await waitFor(() => expect(sentBody).toEqual({ question: "Data science programs?", use_profile: true, search_web: true }));
    expect(await screen.findByText("From the web.")).toBeInTheDocument();
  });
});
