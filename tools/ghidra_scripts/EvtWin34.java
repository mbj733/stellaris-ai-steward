// EvtWin34: 真 vtable 0x14257C130 全表 + COL/TD 类名反查
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin34 extends GhidraScript {

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
        long vt = 0x14257C130L;
        long imgBase = currentProgram.getImageBase().getOffset();
        println("==== vtable @0x" + Long.toHexString(vt) + "（含 -8 槽 COL 反查）====");
        try {
            long colVa = getLong(toAddr(vt - 8));
            println("  [vt-8] = 0x" + Long.toHexString(colVa));
            if (colVa > 0x140000000L && colVa < 0x150000000L) {
                int sig = getInt(toAddr(colVa));
                int tdRva = getInt(toAddr(colVa + 0xC));
                println("  COL sig=" + sig + " tdRva=0x" + Integer.toHexString(tdRva));
                String name = readCStr(imgBase + (tdRva & 0xffffffffL) + 0x10, 160);
                println("  ★ 类名: " + name);
            }
        } catch (Exception e) {
            println("  (COL 读取失败: " + e + ")");
        }
        for (int k = 0; k < 40; k++) {
            try {
                long fn = getLong(toAddr(vt + 8L * k));
                if (fn < 0x140000000L || fn > 0x150000000L) {
                    println("  [" + k + "] 0x" + Long.toHexString(fn) + " (非代码，停止)");
                    break;
                }
                Function f = getFunctionContaining(toAddr(fn));
                println("  [" + k + "] 0x" + Long.toHexString(fn) + "  " + (f != null ? f.getName() : "?"));
            } catch (Exception e) {
                break;
            }
        }
        println("==== done ====");
    }
}
