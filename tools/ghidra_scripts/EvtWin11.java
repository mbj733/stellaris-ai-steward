// EvtWin11: 字符串工具族签名 + 执行器调用点汇编
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class EvtWin11 extends GhidraScript {

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    void asmAt(long va, int before, int after) {
        println("==== asm @0x" + Long.toHexString(va) + " ====");
        Instruction ins = getInstructionAt(toAddr(va));
        if (ins == null) {
            for (long probe = va - 0x60; probe <= va; probe += 1) {
                ins = getInstructionAt(toAddr(probe));
                if (ins != null && ins.getAddress().getOffset() <= va && va <= ins.getMaxAddress().getOffset()) {
                    break;
                }
                ins = null;
            }
        }
        if (ins == null) {
            println("  (no instruction)");
            return;
        }
        for (int i = 0; i < before; i++) {
            Instruction p = ins.getPrevious();
            if (p == null) {
                break;
            }
            ins = p;
        }
        for (int i = 0; i < before + after; i++) {
            println("   " + ins.getAddress() + "  " + ins);
            ins = ins.getNext();
            if (ins == null) {
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x14015af40L, 90);
        decompileFn(0x14015af80L, 60);
        decompileFn(0x14015bcf0L, 70);
        decompileFn(0x14015b980L, 50);
        asmAt(0x141b1322cL, 22, 4);
        asmAt(0x141b1ec6bL, 22, 4);
        println("==== done ====");
    }
}
