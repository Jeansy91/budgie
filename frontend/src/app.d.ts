declare global {
	namespace App {
		interface PageState {
			/** Id of the transaction shown in the detail panel (shallow routing) */
			tx?: number;
		}
	}
}
export {};
