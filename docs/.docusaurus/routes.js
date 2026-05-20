import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/__docusaurus/debug',
    component: ComponentCreator('/__docusaurus/debug', '5ff'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/config',
    component: ComponentCreator('/__docusaurus/debug/config', '5ba'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/content',
    component: ComponentCreator('/__docusaurus/debug/content', 'a2b'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/globalData',
    component: ComponentCreator('/__docusaurus/debug/globalData', 'c3c'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/metadata',
    component: ComponentCreator('/__docusaurus/debug/metadata', '156'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/registry',
    component: ComponentCreator('/__docusaurus/debug/registry', '88c'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/routes',
    component: ComponentCreator('/__docusaurus/debug/routes', '000'),
    exact: true
  },
  {
    path: '/',
    component: ComponentCreator('/', '0cd'),
    routes: [
      {
        path: '/',
        component: ComponentCreator('/', 'ca6'),
        routes: [
          {
            path: '/',
            component: ComponentCreator('/', 'eaa'),
            routes: [
              {
                path: '/advanced/context-propagation',
                component: ComponentCreator('/advanced/context-propagation', '6d3'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/advanced/custom-clients',
                component: ComponentCreator('/advanced/custom-clients', 'e51'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/advanced/prompt-versioning',
                component: ComponentCreator('/advanced/prompt-versioning', '661'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/backend/api-reference',
                component: ComponentCreator('/backend/api-reference', 'c5c'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/backend/database',
                component: ComponentCreator('/backend/database', '598'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/backend/overview',
                component: ComponentCreator('/backend/overview', 'b8f'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/dashboard/overview',
                component: ComponentCreator('/dashboard/overview', '954'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/deployment/docker',
                component: ComponentCreator('/deployment/docker', '8ef'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/deployment/environment-variables',
                component: ComponentCreator('/deployment/environment-variables', '351'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/getting-started/configuration',
                component: ComponentCreator('/getting-started/configuration', '8f7'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/getting-started/installation',
                component: ComponentCreator('/getting-started/installation', '4f1'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/getting-started/quickstart',
                component: ComponentCreator('/getting-started/quickstart', '6cd'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/evaluations',
                component: ComponentCreator('/sdk/evaluations', '7af'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/llm-step',
                component: ComponentCreator('/sdk/llm-step', '01d'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/overview',
                component: ComponentCreator('/sdk/overview', '1d5'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/replay',
                component: ComponentCreator('/sdk/replay', 'b35'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/step',
                component: ComponentCreator('/sdk/step', '403'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/tracing',
                component: ComponentCreator('/sdk/tracing', '9d4'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/sdk/workflow',
                component: ComponentCreator('/sdk/workflow', '1be'),
                exact: true,
                sidebar: "mainSidebar"
              },
              {
                path: '/',
                component: ComponentCreator('/', 'e98'),
                exact: true,
                sidebar: "mainSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
