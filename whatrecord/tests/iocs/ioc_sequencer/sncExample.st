/*************************************************************************\
This file is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
\*************************************************************************/
program snctest
option +r;
float v;
assign v to "{user}:xxxExample";
monitor v;

ss ss1
{
	state low
	{
	    when(v>5.0)
	    {
		printf("now changing to high\n");
	    } state high
	    when(delay(.1))
	    {
	    } state low
	}
	state high
	{
	    when(v<=5.0)
	    {
		printf("changing to low\n");
	    } state low
	    when(delay(.1))
	    {
	    } state high
	}
}
