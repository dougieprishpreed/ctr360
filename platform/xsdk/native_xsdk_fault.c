/* xSDK has no fault handler yet (its milestone 40 plans one). A CPU fault,
 * such as a store through a null pointer, ends the title and the console is
 * back at the dashboard within about two seconds; default.log just stops. */
void Platform_InstallFaultHandler(void) {}
