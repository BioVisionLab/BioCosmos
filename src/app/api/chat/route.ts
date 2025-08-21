// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { OpenAI } from 'openai';
import { openai } from '@ai-sdk/openai';
import { streamText } from 'ai';

// IMPORTANT! Set the runtime to edge
export const runtime = 'edge';

// Check if the OPENAI_API_KEY environment variable is set at module load time
if (!process.env.OPENAI_API_KEY) {
  console.error("CRITICAL: Missing OPENAI_API_KEY at module load time.");
  throw new Error('Missing OPENAI_API_KEY environment variable');
}

export async function POST(req: Request) {
  console.log("--- Chat API Route Started ---");
  try {
    // No need to read apiKey again here, should be handled by the openai provider
    
    const { messages } = await req.json();
    console.log("Parsed messages:", messages);

    // Basic validation
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      console.log("Validation failed: Invalid messages array");
      return new Response('Invalid request body: messages array is required.', { status: 400 });
    }

    console.log("Attempting to call streamText (using implicit API key)...");
    // Use streamText with the Vercel OpenAI provider
    const result = await streamText({
      model: openai('gpt-4o'), // Use gpt-4o model
      messages: messages,
      // No explicit apiKey needed here
    });
    console.log("streamText call completed successfully.");

    // Respond with the stream using the corrected method
    console.log("Returning data stream response...");
    return result.toDataStreamResponse();

  } catch (error) {
    // This log should definitely appear if an exception is caught
    console.error("!!! ERROR CAUGHT in chat API route:", error); 
    // Simplify error handling for now, can add specific OpenAI checks later if needed
    if (error instanceof Error) {
      return new Response(`Error: ${error.message}`, { status: 500 });
    } else {
      return new Response('An unknown error occurred', { status: 500 });
    }
  }
} 