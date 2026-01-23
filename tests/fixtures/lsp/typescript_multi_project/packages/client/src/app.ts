/**
 * Main application demonstrating cross-file method calls.
 * Line 3: app.ts file
 */
import { AuthService } from './auth';
import { formatDate } from './utils';

/**
 * Entry point with cross-file calls.
 * Line 10: main function definition
 * Line 14: main → AuthService.create (cross-file, function→static)
 * Line 15: main → auth.login (cross-file, function→instance method)
 * Line 16: main → formatDate (cross-file, function→function)
 */
export function main(): void {
    const auth = AuthService.create();
    const result = auth.login('testuser');
    const date = formatDate();
    console.log(`Login: ${result}, Date: ${date}`);
}

/**
 * Process a user with cross-file call.
 * Line 22: processUser function definition
 * Line 26: processUser → AuthService constructor (cross-file)
 * Line 27: processUser → auth.login (cross-file)
 */
export function processUser(username: string): boolean {
    const auth = new AuthService();
    return auth.login(username);
}

// Run main if executed directly
main();
