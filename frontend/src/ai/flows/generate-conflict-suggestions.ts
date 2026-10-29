'use server';
/**
 * @fileOverview A Genkit flow for generating AI-powered suggestions for resolving conflicts.
 *
 * - generateConflictSuggestions - A function that handles the generation of conflict resolution suggestions.
 * - GenerateConflictSuggestionsInput - The input type for the generateConflictSuggestions function.
 * - GenerateConflictSuggestionsOutput - The return type for the generateConflictSuggestions function.
 */

import {ai} from '@/ai/genkit';
import {z} from 'genkit';

const GenerateConflictSuggestionsInputSchema = z.object({
  type: z.string().describe('The type of conflict (e.g., "solapamiento horario", "profesor sin carga completa").'),
  title: z.string().describe('A brief title for the conflict.'),
  description: z.string().describe('A detailed description of the conflict.'),
  severity: z.enum(['LOW', 'MEDIUM', 'HIGH']).describe('The severity of the conflict.'),
  suggestedAction: z.string().optional().describe('An initial suggested action from the system, if available.'),
});
export type GenerateConflictSuggestionsInput = z.infer<typeof GenerateConflictSuggestionsInputSchema>;

const GenerateConflictSuggestionsOutputSchema = z.object({
  suggestion: z.string().describe('An AI-powered suggestion for resolving the conflict.'),
});
export type GenerateConflictSuggestionsOutput = z.infer<typeof GenerateConflictSuggestionsOutputSchema>;

export async function generateConflictSuggestions(input: GenerateConflictSuggestionsInput): Promise<GenerateConflictSuggestionsOutput> {
  return generateConflictSuggestionsFlow(input);
}

const conflictSuggestionPrompt = ai.definePrompt({
  name: 'conflictSuggestionPrompt',
  input: {schema: GenerateConflictSuggestionsInputSchema},
  output: {schema: GenerateConflictSuggestionsOutputSchema},
  prompt: `You are an expert in university academic management and conflict resolution.

Given the following conflict details, provide a concise and actionable suggestion for its resolution. The suggestion should be practical and aim to mitigate the issue in the teaching assignment process.

Conflict Type: {{{type}}}
Title: {{{title}}}
Description: {{{description}}}
Severity: {{{severity}}}

{{#if suggestedAction}}
Initial System Suggestion: {{{suggestedAction}}}
{{/if}}

Based on this information, provide an AI-powered suggestion for resolution.`,
});

const generateConflictSuggestionsFlow = ai.defineFlow(
  {
    name: 'generateConflictSuggestionsFlow',
    inputSchema: GenerateConflictSuggestionsInputSchema,
    outputSchema: GenerateConflictSuggestionsOutputSchema,
  },
  async (input) => {
    const {output} = await conflictSuggestionPrompt(input);
    return output!;
  }
);
