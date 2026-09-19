import { z } from "zod";

export const loginSchema = z.object({
  email: z
    .email("Enter a valid email address")
    .min(3, "Email is required")
    .max(320, "Email is too long"),
  password: z.string().min(1, "Password is required").max(1024, "Password is too long"),
});

export type LoginInput = z.input<typeof loginSchema>;
export type LoginValues = z.output<typeof loginSchema>;
