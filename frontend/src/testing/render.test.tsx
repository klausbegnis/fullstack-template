import { useQuery } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

function Greeting() {
  const { data, status } = useQuery({
    queryKey: ["greeting"],
    queryFn: async () => {
      const response = await fetch("https://example.test/greeting");
      return (await response.json()) as { name: string };
    },
  });

  if (status === "pending") return <p>Loading</p>;
  if (status === "error") return <p>Failed</p>;
  return <p>Hello, {data.name}</p>;
}

describe("renderWithProviders", () => {
  it("wires a QueryClientProvider so a component can fetch through MSW", async () => {
    server.use(http.get("https://example.test/greeting", () => HttpResponse.json({ name: "Ada" })));

    renderWithProviders(<Greeting />);

    expect(await screen.findByText("Hello, Ada")).toBeInTheDocument();
  });
});
