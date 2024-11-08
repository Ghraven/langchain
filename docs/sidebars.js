/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 * @format
 */

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */

module.exports = {
  docs: [
    {
      type: "doc",
      label: "Introduction",
      id: "introduction",
    },
    {
      type: "category",
      link: {type: 'doc', id: 'tutorials/index'},
      label: "Tutorials",
      collapsible: false,
      items: [{
        type: 'autogenerated',
        dirName: 'tutorials',
        className: 'hidden',
      }],
    },
    {
      type: "category",
      link: {type: 'doc', id: 'how_to/index'},
      label: "How-to guides",
      collapsible: false,
      items: [{
        type: 'autogenerated',
        dirName: 'how_to',
        className: 'hidden',
      }],
    },
    {
      type: "category",
      link: {type: 'doc', id: 'concepts/index'},
      label: "Conceptual guide",
      collapsible: false,
      items: [{
        type: 'autogenerated',
        dirName: 'concepts',
        className: 'hidden',
      }],
    },
    {
      type: "category",
      label: "Ecosystem",
      collapsed: false,
      collapsible: false,
      items: [
        {
          type: "link",
          href: "https://docs.smith.langchain.com/",
          label: "🦜🛠️ LangSmith"
        },
        {
          type: "link",
          href: "https://langchain-ai.github.io/langgraph/",
          label: "🦜🕸️ LangGraph"
        },
      ],
    },
    {
      type: "category",
      label: "Versions",
      collapsed: false,
      collapsible: false,
      items: [
        {
          type: 'doc',
          id: 'versions/v0_3/index',
          label: "v0.3",
        },
        {
          type: "category",
          label: "v0.2",
          items: [{
            type: 'autogenerated',
            dirName: 'versions/v0_2',
          }],
        },
        {
          type: 'doc',
          id: "how_to/pydantic_compatibility",
          label: "Pydantic compatibility",
        },
        {
          type: "category",
          label: "Migrating from v0.0 chains",
          link: {type: 'doc', id: 'versions/migrating_chains/index'},
          collapsible: false,
          collapsed: false,
          items: [{
            type: 'autogenerated',
            dirName: 'versions/migrating_chains',
            className: 'hidden',
          }],
        },
        {
          type: "category",
          label: "Upgrading to LangGraph memory",
          link: {type: 'doc', id: 'versions/migrating_memory/index'},
          collapsible: false,
          collapsed: false,
          items: [{
            type: 'autogenerated',
            dirName: 'versions/migrating_memory',
            className: 'hidden',
          }],
        },
        "versions/release_policy",
      ],
    },
    "security"
  ],
  integrations: [
    {
      type: "category",
      label: "Providers",
      collapsible: false,
      items: [
        {
          type: "doc",
          id: "integrations/providers/anthropic",
        },
        {
          type: "doc",
          id: "integrations/providers/aws",
        },
        {
          type: "doc",
          id: "integrations/providers/google",
        },
        {
          type: "doc",
          id: "integrations/providers/huggingface",
        },
        {
          type: "doc",
          id: "integrations/providers/microsoft",
        },
        {
          type: "doc",
          id: "integrations/providers/openai",
        },
        {
          type: "category",
          label: "More",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/providers",
              className: "hidden",
            },
          ],
          link: {
            type: "generated-index",
            slug: "integrations/providers/all",
          },
        },
      ],
      link: {
        type: "doc",
        id: "integrations/providers/index",
      },
    },
    {
      type: "category",
      label: "Components",
      collapsible: false,
      items: [
        {
          type: "category",
          label: "Chat models",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/chat",
              className: "hidden",
            },
          ],
          link: {
            type: "doc",
            id: "integrations/chat/index",
          },
        },
        {
          type: "category",
          label: "Embedding models",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/text_embedding",
              className: "hidden",
            },
          ],
          link: {
            type: "doc",
            id: "integrations/text_embedding/index",
          },
        },
        {
          type: "category",
          label: "Document loaders",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/document_loaders",
              className: "hidden",
            },
          ],
          link: {
            type: "doc",
            id: "integrations/document_loaders/index",
          },
        },
        {
          type: "category",
          label: "Vector stores",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/vectorstores",
              className: "hidden",
            },
          ],
          link: {
            type: "doc",
            id: "integrations/vectorstores/index",
          },
        },
        {
          type: "category",
          label: "Retrievers",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/retrievers",
              className: "hidden",
            },
          ],
          link: {
            type: "doc",
            id: "integrations/retrievers/index",
          },
        },
        {
          type: "category",
          label: "Tools/Toolkits",
          collapsible: false,
          items: [
            {
              type: "autogenerated",
              dirName: "integrations/tools",
              className: "hidden",
            },
          ],
          link: {
            type: "doc",
            id: "integrations/tools/index",
          },
        },
        {
          type: "category",
          label: "Other",
          collapsed: true,
          items: [
            {
              type: "category",
              label: "LLMs",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/llms",
                  className: "hidden",
                },
              ],
              link: {
                type: "doc",
                id: "integrations/llms/index",
              },
            },
            {
              type: "category",
              label: "Key-value stores",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/stores",
                  className: "hidden",
                },
              ],
              link: {
                type: "doc",
                id: "integrations/stores/index",
              },
            },
            {
              type: "category",
              label: "Document transformers",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/document_transformers",
                  className: "hidden",
                },
              ],
              link: {
                type: "generated-index",
                slug: "integrations/document_transformers",
              },
            },
            "integrations/llm_caching",
            {
              type: "category",
              label: "Graphs",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/graphs",
                  className: "hidden",
                },
              ],
              link: {
                type: "generated-index",
                slug: "integrations/graphs",
              },
            },
            {
              type: "category",
              label: "Message histories",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/memory",
                  className: "hidden",
                },
              ],
              link: {
                type: "generated-index",
                slug: "integrations/memory",
              },
            },
            {
              type: "category",
              label: "Callbacks",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/callbacks",
                  className: "hidden",
                },
              ],
              link: {
                type: "generated-index",
                slug: "integrations/callbacks",
              },
            },
            {
              type: "category",
              label: "Chat loaders",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/chat_loaders",
                  className: "hidden",
                },
              ],
              link: {
                type: "generated-index",
                slug: "integrations/chat_loaders",
              },
            },
            {
              type: "category",
              label: "Adapters",
              collapsible: false,
              items: [
                {
                  type: "autogenerated",
                  dirName: "integrations/adapters",
                  className: "hidden",
                },
              ],
              link: {
                type: "generated-index",
                slug: "integrations/adapters",
              },
            },
          ],
        },
        
      ],
      link: {
        type: "generated-index",
        slug: "integrations/components",
      },
    },
  ],
  contributing: [
    {
      type: "doc",
      label: "Welcome Contributors",
      id: "contributing/index",
    },
    {
      type: "category",
      link: {type: 'doc', id: 'contributing/tutorials/index'},
      label: "Tutorials",
      collapsible: false,
      items: [{
        type: 'autogenerated',
        dirName: 'contributing/tutorials',
        className: 'hidden',
      }],
    },
    {
      type: "category",
      link: {type: 'doc', id: 'contributing/how_to/index'},
      label: "How-to guides",
      collapsible: false,
      items: [{
        type: 'autogenerated',
        dirName: 'contributing/how_to',
        className: 'hidden',
      }],
    },
    {
      type: "category",
      link: {type: 'doc', id: 'contributing/reference/index'},
      label: "Reference & FAQ",
      collapsible: false,
      items: [{
        type: 'autogenerated',
        dirName: 'contributing/reference',
        className: 'hidden',
      }],
    },
  ],
};
