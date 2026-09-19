import { z } from "zod";

export const userRoleSchema = z.enum(["admin", "member"]);

export const createUserSchema = z.object({
  name: z.string().min(1, "Name is required").max(160, "Name is too long"),
  email: z
    .email("Enter a valid email address")
    .min(3, "Email is required")
    .max(320, "Email is too long"),
  password: z.string().min(1, "Password is required").max(1024, "Password is too long"),
  role: userRoleSchema.default("member"),
});

export type CreateUserInput = z.input<typeof createUserSchema>;
export type CreateUserValues = z.output<typeof createUserSchema>;

export const updateUserSchema = z.object({
  name: z.string().min(1, "Name is required").max(160, "Name is too long"),
  email: z
    .email("Enter a valid email address")
    .min(3, "Email is required")
    .max(320, "Email is too long"),
  role: userRoleSchema,
});

export type UpdateUserInput = z.input<typeof updateUserSchema>;
export type UpdateUserValues = z.output<typeof updateUserSchema>;
