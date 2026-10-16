// 弄清 human_ai 标志(0x142814839)读取方 FUN_140a98c80 的语义 + combat_debug 标志读取方
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class FlagSemantics extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        for (long a : new long[] { 0x140a98c80L }) {
            Function f = getFunctionContaining(toAddr(a));
            if (f == null) {
                continue;
            }
            println("==== decompile FUN_140a98c80 (" + f.getEntryPoint() + ") head ====");
            DecompileResults res = dec.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, 90); i++) {
                    println("  " + lines[i]);
                }
            }
        }
        println("==== readers of combat_debug flag 0x143111210 ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x143111210L))) {
            if (n++ >= 8) {
                break;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() : "?"));
        }
        println("==== readers of 0x1431146f8 (game_paused false 副作用之一) ====");
        n = 0;
        for (Reference r : getReferencesTo(toAddr(0x1431146f8L))) {
            if (n++ >= 8) {
                break;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() : "?"));
        }
        println("==== strings near 0x1422fe0f0 ====");
        ghidra.program.model.address.Address a2 = toAddr(0x1422fe0f0L);
        ghidra.program.model.address.Address end = toAddr(0x1422fe1d0L);
        while (a2.getOffset() < end.getOffset()) {
            ghidra.program.model.listing.Data d = getDataAt(a2);
            if (d != null && d.hasStringValue()) {
                println("  " + a2 + " = " + d.getValue());
            }
            a2 = a2.add(1);
        }
        println("==== done ====");
    }
}
