import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebars: SidebarsConfig = {
  mainSidebar: [
    {
      type: "doc",
      id: "intro",
      label: "What is TraceChain?",
    },
    {
      type: "category",
      label: "Getting Started",
      collapsed: false,
      items: [
        "getting-started/installation",
        "getting-started/quickstart",
        "getting-started/cli",
        "getting-started/configuration",
      ],
    },
    {
      type: "category",
      label: "Python SDK",
      items: [
        "sdk/overview",
        "sdk/workflow",
        "sdk/step",
        "sdk/llm-step",
        "sdk/evaluations",
        "sdk/replay",
        "sdk/tracing",
      ],
    },
    {
      type: "category",
      label: "Backend API",
      items: [
        "backend/overview",
        "backend/api-reference",
        "backend/database",
      ],
    },
    {
      type: "category",
      label: "Dashboard",
      items: [
        "dashboard/overview",
      ],
    },
    {
      type: "category",
      label: "Deployment",
      items: [
        "deployment/docker",
        "deployment/environment-variables",
      ],
    },
    {
      type: "category",
      label: "Advanced",
      items: [
        "advanced/opentelemetry",
        "advanced/custom-clients",
        "advanced/context-propagation",
        "advanced/prompt-versioning",
      ],
    },
  ],
};

export default sidebars;
