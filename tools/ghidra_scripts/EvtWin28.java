// EvtWin28: FUN_14107b1d0 的引用/vtable 定位 + COL/TD 反查类名
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin28 extends GhidraScript {

    String readCStr(long va, int max) {
        StringBuilder sb = new StringBuilder();
        try {
            for (int i = 0; i < max; i++) {
                int b = getByte(toAddr(va + i)) & 0xff;
                if (b == 0) {
                    break;
                }
                if (b < 32 || b > 126) {
                    break;
                }
                sb.append((char) b);
            }
        } catch (Exception e) {
        }
        return sb.toString();
    }

    @Override
    public void run() throws Exception {
        println("==== refs to FUN_14107b1d0 ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x14107b1d0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + " in " + (f != null ? f.getName() : "?"));
            if (++n >= 20) {
                println("  ...");
                break;
            }
        }
        println("==== refs to FUN_1408e5d20 ====");
        n = 0;
        for (Reference r : getReferencesTo(toAddr(0x1408e5d20L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + " in " + (f != null ? f.getName() : "?"));
            if (++n >= 20) {
                println("  ...");
                break;
            }
        }
        println("==== done ====");
    }
}
