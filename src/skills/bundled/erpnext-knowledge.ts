import { registerBundledSkill } from '../bundledSkills.js'
import { getERPNextModuleKnowledge } from './erpnext-knowledge-content.js'

export function registerERPNextKnowledgeSkill(): void {
  registerBundledSkill({
    name: 'erpnext-knowledge',
    description:
      'Load ERPNext/Frappe module reference knowledge. Use when building or debugging ERPNext custom apps. Covers: DocTypes, hooks, permissions, controllers, bench CLI, Query Builder, CRM, Selling, Buying, Stock, Accounting, Manufacturing, HR, Projects, Support.',
    location: 'bundled',
    userInvocable: true,
    async getPromptForCommand(args: string): Promise<string> {
      return getERPNextModuleKnowledge(args)
    },
  })
}
