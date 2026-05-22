import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

const config: Config = {
  title: "TraceChain",
  tagline: "Reliability-first observability for LLM workflows",
  favicon: "img/favicon.ico",

  url: "https://Aarthicjujjavarapu.github.io",
  baseUrl: "/tracechain/",

  organizationName: "Aarthicjujjavarapu",
  projectName: "tracechain",

  trailingSlash: false,

  onBrokenLinks: "throw",

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: "warn",
    },
  },

  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: "./sidebars.ts",
          routeBasePath: "/",
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: "dark",
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: "TraceChain",
      logo: {
        alt: "TraceChain Logo",
        src: "img/logo.svg",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "mainSidebar",
          position: "left",
          label: "Docs",
        },
        {
          href: "https://github.com/Aarthicjujjavarapu/tracechain",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Docs",
          items: [
            { label: "Getting Started", to: "/getting-started/installation" },
            { label: "SDK Reference", to: "/sdk/overview" },
            { label: "API Reference", to: "/backend/api-reference" },
          ],
        },
        {
          title: "Project",
          items: [
            { label: "GitHub", href: "https://github.com/Aarthicjujjavarapu/tracechain" },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} TraceChain.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ["bash", "python", "typescript", "json", "yaml", "docker"],
    },
    algolia: undefined,
  } satisfies Preset.ThemeConfig,
};

export default config;
