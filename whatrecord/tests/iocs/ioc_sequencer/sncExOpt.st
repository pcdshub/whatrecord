/*************************************************************************\
This file is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
\*************************************************************************/
program snctest
float v;
assign v to "{user}:xxxExample";
monitor v;

ss ss1
{
	state low
	{
            option +t; /* The default is +t, so thsi has no effect */
	    entry
	    {
		printf("Will do this on entry");
		printf("Another thing to do on entry");
	    }
	    when(v>5.0)
	    {
		printf("now changing to high\n");
	    } state high
	    when(delay(.1))
	    {
		/* Pause of .1 on every iteration */
	    } state low
	}
	state high
	{
            option -t;
	    when(v<=5.0)
	    {
		printf("changing to low\n");
	    } state low
	    when(delay(.1))
	    {
		/* After 1st pause of .1 sec, state high will enter a tight loop
                   entering this condition on each iteration until v is
                   set to less <= 5.0 */
	    } state high
	}
}
